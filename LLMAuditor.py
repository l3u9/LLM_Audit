import requests
import json
import collections
import re

class LLMAuditor:
    def __init__(self, api_ip="localhost", model="deepseek-r1-distill-qwen-32b",
                 max_tokens=50000, temperature=0.8, top_p=0.5, num_samples=5):
        self.api_url = f"http://{api_ip}:1234/v1/completions"
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.num_samples = num_samples  # Self-Consistency 적용

    # def formatting_datas(self, datas, modifiers):
        
    #     # enumerate loop using dict
    #     formatted = ""

    #     for i, (key, value) in enumerate(modifiers.items()):
    #         formatted += f"#### Modifier Function {i}\n\n"
    #         formatted += f"Contract Name: {key}\n\n"
    #         formatted += "\n\nFunction Code: \n"
    #         formatted += "\n".join(value)

    #     for i, (key, value) in enumerate(datas.items()):

    #         if i == 0:
    #             formatted += "#### Entry Function\n\n"
    #             formatted += f"Contract Name: {key}\n\n"
    #             for val in value:
    #                 formatted += "\n\nFunction Code: \n"
    #                 formatted += "\n".join(val)
    #         else:
    #             formatted += f"\n\n#### Dependent Function {i}\n\n"
    #             formatted += f"Contract Name: {key}\n\n"
    #             for val in value:
    #                 formatted += "\n\nFunction Code: \n"
    #                 formatted += "\n".join(val)


    #     return formatted
    
    def set_api_ip(self, api_ip):
        self.api_url = f"http://{api_ip}:1234/v1/completions"

    def set_context_length(self, max_tokens):
        self.max_tokens = max_tokens
    
    def set_temperature(self, temperature):
        self.temperature = temperature
    
    def set_top_p(self, top_p):
        self.top_p = top_p
    
    def set_num_samples(self, num_samples):
        self.num_samples = num_samples

    def formatting_datas(self, datas, impacted_functions=None):
        
        # enumerate loop using dict
        formatted = ""

        for i, (key, value) in enumerate(datas.items()):

            if i == 0:
                formatted += "#### Entry Function\n\n"
                formatted += f"Contract Name: {key}\n\n"

                formatted += "\n\nFunction Code: \n"
                formatted += "\n".join(value[0])

                if len(value) > 1:
                    formatted += f"\n\n#### Dependent Function {i+1}\n\n"
                    formatted += f"Contract Name: {key}\n\n"
                    for val in value[1:]:
                        formatted += "\n\nFunction Code: \n"
                        formatted += "\n".join(val)

            else:
                formatted += f"\n\n#### Dependent Function {i+1}\n\n"
                formatted += f"Contract Name: {key}\n\n"
                for val in value:
                    formatted += "\n\nFunction Code: \n"
                    formatted += "\n".join(val)

        if impacted_functions:
            for i, (key, value) in enumerate(impacted_functions.items()):
                if len(value) > 0:
                    formatted += f"\n\n#### Impacted Function {i+1}\n\n"
                    formatted += f"Contract Name: {key}\n\n"
                    for val in value:
                        formatted += "\n\nFunction Code: \n"
                        formatted += "\n".join(val)


        return formatted


    def _parse_decision(self, results):
        """Result 값을 파싱하여 취약 여부 결정"""
        match = re.search(r"Result:\s*([^-]+)", results)  # 'Result:' 다음의 문자열 추출
        if match:
            result_value = match.group(1).strip()
            if "Vulnerable" in result_value:
                return "Vulnerable"
            else:
                return "Secure"
        return None
    

    def _parse_keywords(self, results):
        match = re.search(r"Keywords:\s*(.*)", results)
        if match:
            keywords = match.group(1)
            
            # 'Code Line(s): [Line 3]' 형식에서 라인 번호 파싱
            line_match = re.search(r"Code Line\(s\): \[([^\]]+)\]", results)
            if line_match:
                line_numbers = line_match.group(1).split(",")  # 여러 라인 번호를 쉼표로 구분하여 리스트로 변환
                line_numbers = [line.strip() for line in line_numbers]  # 불필요한 공백 제거
                return keywords, line_numbers  # 키워드와 라인번호 리스트 반환
            
            return keywords, None
        return None, None


    def decision_prompt(self, contracts): 
        cot_prompt = f"""
You are a senior smart contract security auditor with a track record in Code4rena contest audits. 
Your task is to analyze the following Solidity smart contracts and identify only vulnerabilities that 
are realistically exploitable (Medium or High risk). Do NOT report vulnerabilities that are purely 
theoretical or unlikely to be triggered, and do NOT provide any recommendations or mitigation strategies.

---
### Analysis Process (Chain-of-Thought Approach)
Follow these structured steps to ensure accurate vulnerability identification:

1. **Step 1: Identify Each Function's Intent & Expected Behavior**
   - For **each** function (Entry, Dependent, or Impacted), determine its intended purpose, 
     expected inputs/outputs, and expected state changes.
   - Check if the actual implementation aligns with this intended behavior.
   - Look for access control misconfigurations, improper parameter validation, or unintended 
     side effects that could introduce vulnerabilities.

2. **Step 2: Evaluate Cross-Function Interactions & State Modifications**
   - Analyze how Entry/Dependent functions modify the contract state and determine if any function 
     call sequences can lead to incorrect or maliciously exploitable states.
   - If a bug in one function (e.g., missing access checks) propagates to another function, 
     explain how it can be exploited in practice.
   - Check whether external calls combined with state changes result in security flaws.

3. **Step 3: Construct Realistic Attack Scenarios**
   - Identify clear, practical attack paths that an adversary could exploit.
   - Ensure that vulnerabilities classified as Medium or High risk are **demonstrably exploitable** 
     under real-world conditions.
   - If an issue is identified but lacks a direct attack vector, it should **not** be classified as Medium/High risk.

---
### 1. Smart Contract Security & Logic Analysis
Examine how functions modify the contract state and whether function calls can be chained to cause unintended 
side effects, privilege escalations, or asset compromise.

#### Key Areas to Focus On:
- How do different functions modify the contract state, and can these state changes be exploited across calls?
- Identify execution sequences that could result in unintended asset compromise or functional disruptions.
- Evaluate whether interactions between functions introduce vulnerabilities that may not be apparent in isolation.
- Assess external calls within function execution and determine if they introduce exploitable attack vectors.

---
### 2. Logical Consistency & Business Logic Validation
- Validate that function logic aligns with its intended purpose.
- Confirm that inputs and outputs are processed correctly without hidden exploitation opportunities.
- Scrutinize loops, iteration behavior, and execution order to uncover logical flaws.
- Any vulnerability reported must have a **clear, feasible attack path**, comparable to past Code4rena findings.

---
### 3. Realistic Exploitation & Attack Scenarios
For every identified issue, ensure that:
- It can be **realistically exploited** under typical contract conditions.
- It is **not dependent on highly unlikely edge cases** or unrealistic attacker setups.
- It leads to **tangible security risks**, such as financial loss, unauthorized access, or contract state manipulation.

---
### 4. Handling Reentrancy & State Manipulation
- **Do NOT report reentrancy vulnerabilities** unless they introduce broader **state manipulation risks**.
- If an external call results in unintended contract state changes, it **must be analyzed** for potential impact.
- Any issue related to **unexpected state transitions** or **cross-function exploits** should be included.

---
### 5. Preventing False Secure Classification
A contract should only be classified as **"Secure"** if:
1. No exploitable business logic errors, state inconsistencies, or access control flaws exist.
2. All provided functions have been thoroughly analyzed for realistic attack paths.
3. Any minor inconsistencies do **not** result in significant security risks.

---
### 6. Risk Classification
#### Medium Risk:
- Vulnerabilities where assets are **not immediately at risk** but **realistic exploitation** 
  could cause disruptions, financial losses, or privilege escalations.
- Issues that require **plausible attack conditions** to manifest.

#### High Risk:
- Vulnerabilities that **directly** enable asset theft, loss, or unauthorized control.
- Flaws that can result in **significant financial loss** or complete contract compromise 
  under normal operating conditions.

---
### 7. Result Output Format (Includes Code Line Information)
Each identified vulnerability must include the **affected function name and the exact line number(s)** 
where the issue occurs.  

If the contract has a **High risk vulnerability**:
'''
Result: Vulnerable - High Risk  
Function: <Function Name>  
Code Line(s): [Line Numbers]  
Keywords: [Identified Vulnerability Here]  
'''

If the contract has a **Medium risk vulnerability**:
'''
Result: Vulnerable - Medium Risk  
Function: <Function Name>  
Code Line(s): [Line Numbers]  
Keywords: [Identified Vulnerability Here]  
'''

If the contract has no **Medium or High risk vulnerabilities**, but minor issues exist:
'''
Result: Secure  
'''

---
### 8. Final Output Restriction
- The final output **must only contain the final result** as per the format above.
- **Do not provide any chain-of-thought explanation or reasoning in the final output.**
- However, internally, you must perform structured reasoning to ensure accurate vulnerability classification.

---
### 9. Smart Contracts to Audit:
{contracts}
"""

        return cot_prompt



    # def decision_vuln(self, contracts, modifiers):
    def decision_vuln(self, contracts, impacted_functions=None):
        """ 여러 개의 스마트 컨트랙트 최상위 함수 분석 + Self-Consistency 적용 """
        decisions = []
        keywords = []

        prompt = self.decision_prompt(self.formatting_datas(contracts, impacted_functions))
        threshold = (self.num_samples // 2) + 1
        print("Prompt: ", prompt)

        for _ in range(self.num_samples):
            try:
                payload = {
                    "model": self.model,
                    "prompt": prompt,
                    "max_tokens": self.max_tokens,
                    "temperature": self.temperature,
                    "top_p": self.top_p,
                    "stop": None
                }
                response = requests.post(self.api_url, json=payload)
                response_text = response.json()["choices"][0]["text"].strip()
                
                # decision = self._parse_results(response_text)
                decision_result = self._parse_decision(response_text)
                _keywords = self._parse_keywords(response_text)

                decisions.append(decision_result)
                if _keywords:  # None이 아닌 경우에만 추가
                    keywords.append(_keywords)

                print("Decision: ", decision_result)
                print("Keywords: ", _keywords)

                # 동일한 Decision이 3번 이상 나오면 즉시 반환
                decision_counter = collections.Counter(decisions)
                most_common_decision, count = decision_counter.most_common(1)[0]
                if count >= threshold:
                    print(f"Threshold reached with decision: {most_common_decision}")
                    return most_common_decision, keywords
            
            except Exception as e:
                print("Error: ", e)

        # 최종 결과 반환 시 keywords 리스트에서 None 값 제거
        return collections.Counter(decisions).most_common(1)[0][0], list(filter(None, keywords))
    
    # def review_prompt(self, contracts, modifiers, result):



    def review_prompt(self, contracts, impacted_functions, result):
        """ 리뷰 프롬프트 생성 """

        formatted_contracts = self.formatting_datas(contracts, impacted_functions)

        _review_prompt = f"""
You are a **senior smart contract security reviewer**. Your task is to **verify the vulnerabilities identified by the initial security audit (Auditor)** and determine whether they are **valid**. Your analysis should go beyond theoretical concerns and focus on **realistic exploitability, access control, and system impact**.

---

### 1. Audit Report from Security Analyst
The following vulnerabilities were initially detected by the security auditor:

{result}

These vulnerabilities were flagged as **potential security risks**. Note that the previous auditor has already extracted specific **keywords** highlighting the reasons behind each flagged issue. Your task is to re-evaluate these vulnerabilities by **cross-checking the provided keywords with the actual smart contract code**.

---

### 2. Reviewer Objectives
Your role as a **security reviewer** is to analyze the vulnerabilities from three different perspectives:

- 🔹 **Code Logic Bug:**  
  - Is there an internal logic error causing unintended behavior?
  - Could the code execute incorrectly due to an implementation flaw?

- 🔹 **Business Logic Bug:**  
  - Does the function fail to achieve its intended protocol behavior?
  - Could an attacker **abuse contract functionality** to gain an unfair advantage?
  - Are incentives misaligned, potentially leading to unintended financial gain?

- 🔹 **System Bug:**  
  - Can this vulnerability be exploited to **affect protocol security or stability**?
  - Do external dependencies (oracles, external calls, state updates) introduce a critical issue?
  - Could this issue create **network-wide disruptions or systemic risks**?

**If a function is controlled by a trusted entity, assume they do not act maliciously and adjust risk classification accordingly.**

---

### 3. Smart Contract for Review
Below is the smart contract code that must be reviewed:

```solidity
{formatted_contracts}
```

---

### 4. **Expected Output Format**

If the vulnerability is confirmed:
```
Function: <Function Name>
Result: Confirmed - [Low/Medium/High] Risk
Keywords: [Identified Vulnerabilities]

📌 **Bug Classification:**
- [Code Logic Bug / Business Logic Bug / System Bug]

🔒 **Access Control & Trusted Entity Analysis:**
- Function restricted by: [Modifier / Require Condition]
- Who can execute: [onlyOwner / onlyOperator / Public]
- Is this entity trusted (based on trust assumptions)? [Yes/No]
- If trusted, does this reduce the risk? [Yes/No]

🔍 **Issue Description:**
- [Explain why this vulnerability is valid]

🚨 **Attack Scenario (POC):**
- [Describe how an attacker could exploit this]

🎯 **Impact:**
- [Describe the potential damage to users or protocol]

🛠 **Suggested Fix:**
- [Describe a high-level fix to mitigate the risk]
```

If the vulnerability is a false positive:
```
Function: <Function Name>
Result: False Positive
Keywords: [Reported Vulnerabilities]

❌ **Reason for False Positive:**
- [Explain why the reported issue is not exploitable or is misclassified]
```

---

### 5. **Final Decision Process**
- Analyze each function individually and **validate whether the reported vulnerabilities actually exist.**
- Check **who can execute the function** based on `modifier` or `require` statements.
- Determine if the **executing entity is trusted**:
    - If the entity is **trusted**, assume they do not act maliciously and reduce risk classification.
    - If the entity is **not trusted** (governance-controlled, DAO, external multisig), assume the worst-case scenario.
- If vulnerabilities are **confirmed**, provide a detailed explanation along with a **POC attack scenario**.
- If vulnerabilities are **false positives**, justify why they were incorrectly flagged.

Ensure that your final report is **accurate and based on real security risks**.
        """
        
        return _review_prompt


    def review_vulnerabilities(self, contracts, impacted_functions, result):
        """ 리뷰 """
        try:
            prompt = self.review_prompt(contracts, impacted_functions, result)
            responses = []

            payload = {
                "model": self.model,
                "prompt": prompt,
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "stop": None
            }
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
            result = response.json()["choices"][0]["text"].strip()

            return result
        except Exception as e:
            # recall this function
            print("Error: ", e)


            return self.review_vulnerabilities(contracts, impacted_functions, result)
            


# 🔹 실행 코드
if __name__ == "__main__":
    auditor = LLMAuditor(model="deepseek-r1-distill-qwen-32b")

    contract_data = [
        {
            "contractname": "Vault",
            "entry_function": "function withdraw() public { require(balances[msg.sender] > 0); (bool success, ) = msg.sender.call{value: balances[msg.sender]}(\"\"); require(success); balances[msg.sender] = 0; }",
            "dependencies": [
                "function _transfer(address to, uint256 amount) private { balances[to] += amount; }",
                "function _updateBalance(address user, uint256 amount) internal { balances[user] = amount; }"
            ]
        },
        {
            "contractname": "Token",
            "entry_function": "function transfer(address _to, uint256 _value) public { require(balanceOf[msg.sender] >= _value); balanceOf[msg.sender] -= _value; balanceOf[_to] += _value; }",
            "dependencies": [
                "function _approve(address owner, address spender, uint256 value) internal { allowance[owner][spender] = value; }",
                "function _spendAllowance(address owner, address spender, uint256 value) internal { allowance[owner][spender] -= value; }"
            ]
        }
    ]



    decision, keywords = auditor.decision_vuln(contract_data)





    review = auditor.review_vulnerabilities(contract_data, decision)


