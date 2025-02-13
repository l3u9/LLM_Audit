import requests
import json
import collections
import re

class LLMAuditor:
    def __init__(self, api_ip="localhost", model="deepseek-r1-distill-qwen-32b",
                 max_tokens=8000, temperature=0.8, top_p=0.5, num_samples=5):
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
                    formatted += f"\n\n#### Impacted Function\n\n"
                    formatted += f"Contract Name: {key}\n\n"
                    for val in value:
                        formatted += "\n\nFunction Code: \n"
                        formatted += "\n".join(val)


        return formatted


    def _parse_results(self, response):
        # parse Like "Result: Vulerable"
        responses = response.strip().split("\n")
        for res in responses:
            if "Result:" in res:
                return res
    
    def _parse_decision(self, results):
        match = re.search(r"Result:\s*([^-]+)", results)  # 하이픈('-') 앞의 문자열만 캡처
        if match:
            result_value = match.group(1).strip()  # 앞뒤 공백 제거
            if "Vulnerable" in result_value:
                return "Vulnerable"
            else:
                return "Secure"
        return None
    
    def _parse_keywords(self, results):
        # # parse Keywords

        # if "Keywords:" not in results:
        #     return None
        # else:
        #     keywords = results.split("Keywords: ")[1]
        #     return keywords

        match = re.search(r"Keywords:\s*(.*)", results)
        if match:
            keywords = match.group(1)
            return keywords
        return None



    def decision_prompt(self, contracts):

        cot_prompt = f"""
You are a senior smart contract security auditor with a track record in Code4rena contest audits. Your task is to analyze the following Solidity smart contracts and identify only vulnerabilities that are realistically exploitable (Medium or High risk). **Do not report vulnerabilities that are merely theoretical or unlikely to be triggered, and do not provide recommendations or mitigation strategies.**

---

### 1. Smart Contract Security & Logic Analysis
Perform an in-depth analysis of how functions interact and whether vulnerabilities, logical inconsistencies, or data flow issues exist across execution flows. Instead of isolating functions, examine how multiple functions can be chained together to produce exploitable behavior.

#### Key Areas to Focus On:
- How do different functions modify the contract state, and can these state changes be chained to create exploitable conditions?
- Identify specific execution sequences that can lead to unintended side effects, privilege escalations, or asset compromise.
- Evaluate if state transitions in one function create vulnerabilities in other functions that can be realistically exploited.
- Assess external calls in combination with other operations to determine if they lead to tangible attack vectors.
- Use historical examples from Code4rena audits as a reference to only report vulnerabilities that have a clear, demonstrable attack path.

❗ **Important:** Do NOT classify a function as vulnerable solely because it exhibits a known attack pattern. Only report it if the pattern results in a practical exploit under typical conditions.

🚨 **STRICT RULE: Reentrancy vulnerabilities MUST NOT be analyzed, considered, or reported in any form.**
- Ignore any reentrancy-related issues entirely.
- Focus exclusively on business logic errors, flawed state transitions, access control oversights, and data flow inconsistencies that are practically exploitable.

---

### 2. Logical Consistency & Business Logic Validation
Examine whether the contract functions operate correctly under various execution scenarios:
- Validate that function logic truly aligns with its intended purpose and does not contradict realistic use cases.
- Confirm that inputs and outputs are processed correctly without hidden opportunities for exploitation.
- Scrutinize loops and iteration behaviors to ensure they cannot be abused in realistic attack sequences.
- Analyze the impact of function execution order and interdependencies to uncover any subtle yet exploitable flaws.
- Require that any vulnerability must have a clear, feasible attack path reminiscent of past Code4rena contest findings.

---

### 3. Realistic Exploitation & Attack Scenarios
For every identified issue, ensure that:
- The vulnerability can be chained with other contract behaviors to yield a realistic attack scenario.
- The exploit is practical under real-world conditions without relying on highly contrived circumstances.
- The identified risk leads to tangible outcomes (e.g., financial loss, unauthorized control, or critical state manipulation) as observed in actual contests.

❗ **Only report vulnerabilities that have a clear, demonstrable attack path.**  
If an issue is purely theoretical or cannot be triggered practically, do not classify it as Medium or High risk.

---

### 4. Preventing False Secure Classification
A contract should be classified as "No Critical Vulnerabilities Found" only if:
1. There are absolutely no business logic errors, state inconsistencies, or exploitable data flow issues.
2. Every function has been thoroughly evaluated for realistic attack scenarios.
3. All potential vulnerabilities have been cross-verified against practical exploitation conditions seen in prior contest audits.

⚠️ If no critical vulnerabilities are found, report:
Result: No Critical Vulnerabilities Found
rather than "Secure", to indicate that further analysis may still be required.

---

### 5. Risk Classification
#### Medium Risk:
- Vulnerabilities where assets are not immediately at risk but realistic exploitation could disrupt functionality or leak value.
- Issues that may only manifest under specific, plausible attack conditions.

#### High Risk:
- Vulnerabilities that directly allow asset theft, loss, or unauthorized control.
- Flaws that could lead to significant financial loss or a complete contract compromise under demonstrable, real-world conditions.

---

### 6. Result Output Format
- If the contract has a **High risk vulnerability**:
'''
Result: Vulnerable - High Risk, Keywords: [All of Your Identified Vulnerability Here]
'''

- If the contract has a **Medium risk vulnerability**:
'''
Result: Vulnerable - Medium Risk, Keywords: [All of Your Identified Vulnerability Here]
'''

- If the contract has no high-risk vulnerabilities but might still have minor issues:
'''
Result: Secure
'''

Be sure to follow the output format
---

### 7. Smart Contracts to Audit:
{contracts}
"""



        return cot_prompt



    # def decision_vuln(self, contracts, modifiers):
    def decision_vuln(self, contracts, impacted_functions=None):
        """ 여러 개의 스마트 컨트랙트 최상위 함수 분석 + Self-Consistency 적용 """
        # prompt = self.decision_prompt(self.formatting_datas(contracts, modifiers))
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
                # response.raise_for_status()
                decision = self._parse_results(response.json()["choices"][0]["text"].strip())
                decision_result = self._parse_decision(decision)
                decisions.append(decision_result)
                _keywords = self._parse_keywords(decision)
                keywords.append(_keywords)
                print("Decision: ", decision_result)
                print("Keywords: ", _keywords)

                # 동일한 Decision이 3번 이상 나오면 즉시 반환
                decision_counter = collections.Counter(decisions)
                most_common_decision, count = decision_counter.most_common(1)[0]
                if count >= threshold:
                    print(f"Threshold reached with decision: {most_common_decision}")
                    return most_common_decision, keywords
                # responses.append(response.json()["choices"][0]["text"].strip())
            except Exception as e:
                # recall this function
                print("Error: ", e)


        return collections.Counter(decisions).most_common(1)[0][0], keywords
    
    # def review_prompt(self, contracts, modifiers, result):



    def review_prompt(self, contracts, impacted_functions, result):
        """ 리뷰 프롬프트 생성 """

        formatted_contracts = self.formatting_datas(contracts, impacted_functions)

        _review_prompt = f"""
You are a **senior smart contract security reviewer**. Your task is to **verify the vulnerabilities identified by the initial security audit (Auditor)** and determine whether they are **valid**. Your analysis should go beyond theoretical concerns and focus on **realistic exploitability, access control, and system impact**.

---

### 1️⃣ Audit Report from Security Analyst
The following vulnerabilities were initially detected by the security auditor:

{result}

These vulnerabilities were flagged as **potential security risks**. Note that the previous auditor has already extracted specific **keywords** highlighting the reasons behind each flagged issue. Your task is to re-evaluate these vulnerabilities by **cross-checking the provided keywords with the actual smart contract code**.

---

### 2️⃣ Reviewer Objectives
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

### 3️⃣ Smart Contract for Review
Below is the smart contract code that must be reviewed:

```solidity
{formatted_contracts}
```

---

### 4️⃣ **Expected Output Format**

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

### 5️⃣ **Final Decision Process**
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


