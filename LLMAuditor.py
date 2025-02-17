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
            """여러 개의 'Result:' 값 중 가장 심각한 취약성을 반환"""
            matches = re.findall(r"Result:\s*([^-]+)", results)  # 모든 'Result:' 값 추출
            if not matches:
                return None  # 결과가 없으면 None 반환
            
            decisions = [match.strip() for match in matches]

            # 취약성이 포함된 경우 "Vulnerable" 반환 (우선순위 고려)
            for decision in decisions:
                if f"Vulnerable" in decision:
                    return "Vulnerable"

            # 모든 결과가 "Secure"라면 "Secure" 반환
            return "Secure"


    def _parse_keywords(self, results):
        """Function, Code Line(s), Keywords를 여러 개 처리하여 리스트로 반환"""
        # 각 "Result:" 블록을 분리하여 처리
        result_blocks = re.split(r"\n\nResult:", results)[1:]  # 첫 번째 요소는 공백이므로 무시
        
        parsed_results = []
        
        for block in result_blocks:
            # 개행 문자 제거 및 공백 제거
            block = block.strip()
            
            # Function, Code Line(s), Keywords를 추출
            function_match = re.search(r"Function:\s*(.*?)\n", block)
            code_lines_match = re.search(r"Code Line\(s\):\s*(.*?)(\n|$)", block)  # 수정된 정규표현식
            keywords_match = re.search(r"Keywords:\s*(.*?)(?=\nResult:|$)", block, flags=re.DOTALL)
            
            function_name = function_match.group(1).strip() if function_match else ""
            line_numbers = code_lines_match.group(1).strip() if code_lines_match else ""
            keywords = keywords_match.group(1).strip() if keywords_match else ""
            
            parsed_results.append(([function_name, keywords], line_numbers))
        
        return parsed_results


    
    
    def decision_prompt(self, contracts): 
        cot_prompt = f"""
You are a senior smart contract security auditor with extensive experience in Code4rena contest audits. 
Your task is to analyze the following Solidity smart contracts and identify vulnerabilities that are 
realistically exploitable (Medium or High risk). Do NOT report theoretical or highly improbable issues.

---
### Enhanced Analysis Process (Chain-of-Thought Approach)
Follow these four steps to ensure the detection of logical, contextual, and implementation flaws:

### 1. **Function Intent & Implementation Validation**
   - Identify each function’s intended purpose, expected inputs/outputs, and expected state transitions.
   - Check for misalignments between intent and implementation, including logic bugs, incorrect conditions, 
     and unintended state modifications.
   - Assess whether loop behaviors, execution order, and branching logic create exploitable vulnerabilities.

### 2. **Inter-Function & State Dependency Analysis**
   - Evaluate how each function modifies the contract’s state and how these state changes impact other functions.
   - Identify if state transitions create inconsistencies, unexpected privileges, or unintended function behavior.
   - Analyze whether chaining function calls can lead to privilege escalation, unauthorized state modifications, 
     or asset compromise.

### 3. **Contextual & Business Logic Vulnerability Assessment**
   - Verify that all operations align with their expected business logic and contract context.
   - Identify logical inconsistencies in how values are stored, modified, or transferred.
   - Detect flawed access control mechanisms, unsafe assumptions, and unintended execution paths.

### 4. **Realistic Exploitation & Attack Path Construction**
   - Construct plausible attack paths that leverage discovered vulnerabilities.
   - Confirm that the identified issues lead to tangible exploitability (financial loss, unauthorized access, 
     or state corruption) under practical conditions.
   - Avoid reporting vulnerabilities that require highly improbable execution conditions.

---
### **Key Areas of Focus for Logical, Contextual, and Implementation Bugs**
#### **Logical Bugs (Flaws in Execution & Conditional Logic)**
   - Incorrect condition checks leading to unauthorized access or unintended behavior.
   - Misconfigured loops, incorrect iteration logic, or flawed function execution sequences.
   - Unintended behaviors due to misplaced or missing return statements.

#### **Contextual Bugs (Misalignment Between Intent & Code Execution)**
   - Business logic flaws where expected outcomes do not match real execution.
   - Unhandled edge cases, incomplete access control, or overlooked execution scenarios.
   - State inconsistencies due to unexpected contract interactions or external dependencies.

#### **Implementation Bugs (Directly Exploitable Vulnerabilities)**
   - Insecure state changes that allow unauthorized modifications or fund theft.
   - Flawed access control leading to privilege escalation or asset loss.
   - Critical execution flaws that allow unintended manipulation of contract logic.

---
### **Strict Risk Classification**
Only classify vulnerabilities if they meet realistic attack criteria.

#### **High Risk:**
- Flaws that directly enable fund theft, permanent loss, or unauthorized control.
- Bugs that could cause significant financial impact or render the contract unusable.

#### **Medium Risk:**
- Issues that disrupt core functionality or introduce potential fund leaks.
- State inconsistencies that could lead to privilege escalation under realistic conditions.

---
### **Result Output Format**
- If the contract has a **High risk vulnerability**:
'''
Result: Vulnerable - High Risk, Keywords: [Identified Vulnerability]
'''

- If the contract has a **Medium risk vulnerability**:
'''
Result: Vulnerable - Medium Risk, Keywords: [Identified Vulnerability]
'''

- If the contract has no Medium or High risk vulnerabilities:
'''
Result: Secure
'''

---
### **Strict Output Restriction**
- The final output must contain only the result without any additional explanation or reasoning.
- Only report issues if they are realistically exploitable.
- Assume external calls are made to trusted entities.

---
### **Smart Contracts to Audit:**
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

                # # 동일한 Decision이 3번 이상 나오면 즉시 반환
                # decision_counter = collections.Counter(decisions)
                # most_common_decision, count = decision_counter.most_common(1)[0]
                # if count >= threshold:
                #     print(f"Threshold reached with decision: {most_common_decision}")
                #     return most_common_decision, keywords
            
            except Exception as e:
                print("Error: ", e)

        # 최종 결과 반환 시 keywords 리스트에서 None 값 제거
        return collections.Counter(decisions).most_common(1)[0][0], keywords
    
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


