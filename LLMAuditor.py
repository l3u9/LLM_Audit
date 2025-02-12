import requests
import json
import collections
import re

class LLMAuditor:
    def __init__(self, api_ip="localhost", model="deepseek-r1-distill-qwen-32b",
                 max_tokens=7000, temperature=0.8, top_p=0.5, num_samples=5):
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
                for val in value:
                    formatted += "\n\nFunction Code: \n"
                    formatted += "\n".join(val)
            else:
                formatted += f"\n\n#### Dependent Function {i}\n\n"
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

        # results = results.strip().split("Result: ")[1]
        # result = results.strip().split("-")[0]
        # return result
        match = re.search(r"Result:\s*(.*?)(?=\s*,\s*Keywords:|$)", results)
        if match:
            result_value = match.group(1)
            return result_value
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
You are a senior smart contract security auditor. Your task is to analyze the following Solidity smart contracts and determine whether they contain security vulnerabilities. **Only report vulnerabilities that are Medium or High risk. Do not provide recommendations or mitigation strategies.**

---

### 🔹 **1. Smart Contract Security & Logic Analysis**
For each contract, analyze how functions interact with each other and whether security vulnerabilities, logical inconsistencies, or data flow issues exist based on different execution flows. Instead of just checking individual functions in isolation, consider how multiple functions can be used together in various ways.

#### **Key Areas to Focus On:**
- How do different functions modify the contract state, and can an attacker exploit this?
- Are there execution sequences that could cause unintended side effects or security risks?
- Do any state changes make another function vulnerable to abuse?
- Are there external calls that, when combined with other operations, could create an exploitable condition?
- Could an attacker manipulate function inputs or call functions in a specific order to break the contract logic?

❗ **Important: Do NOT classify a function as vulnerable just because it follows a known attack pattern. Instead, verify whether the pattern actually leads to an exploit or logical failure.**

🚨 **STRICT RULE: Reentrancy vulnerabilities MUST NOT be analyzed, considered, or reported in any form.**
- Even if reentrancy exists in the contract, IGNORE IT and do NOT report it.
- Focus ONLY on business logic errors, incorrect state transitions, access control flaws, and data flow inconsistencies.
- If a function contains a reentrancy pattern but does not have other business logic issues, consider it secure.

---

### 🔹 **2. Logical Consistency & Business Logic Validation**
Beyond security vulnerabilities, examine whether the contract functions operate correctly under different execution scenarios:
- **Does the function logic align with its intended purpose, or is there a contradiction?**
- **Are function inputs and outputs handled correctly, or is data incorrectly processed?**
- **If a function uses loops, are iterations correctly structured, or is there an unintended behavior (e.g., passing an entire array instead of individual elements)?**
- **Does function execution order create unintended side effects on shared state variables?**
- **Do function dependencies rely on assumptions that could be invalidated by another function?**

Think broadly—your goal is not just to check for standard vulnerabilities but also to analyze **how the contract behaves under various real-world conditions** and ensure that function logic is correct.

---

### 🔹 **3. Identifying Data Flow & Execution Issues**
A function may be considered vulnerable if:
1. **It incorrectly processes inputs, leading to unintended side effects or logical errors.**
2. **Loop conditions cause redundant or incorrect external calls, inefficient execution, or logical inconsistencies.**
3. **A function modifies a shared state variable incorrectly, affecting dependent functions.**
4. **A function makes incorrect assumptions about its inputs or state dependencies.**
5. **There are inconsistencies between how a function should work and how it is actually implemented.**

❗ **If a function contains logical errors that could cause unintended behavior, it should be classified as a Medium or High risk vulnerability, depending on its impact.**

---

### 🔹 **4. Preventing False Secure Classification**
A contract should **only** be classified as "Secure" if:
1. **There are NO business logic errors, function execution inconsistencies, or data flow issues.**
2. **All function inputs are handled correctly, and no unexpected side effects occur.**
3. **The contract has been fully analyzed for logical correctness in function execution and state management.**

⚠️ **If no critical vulnerabilities are found, classify the contract as "No Critical Vulnerabilities Found" instead of "Secure" to indicate that while no high-risk issues were detected, further analysis may still be required.**

---

### 🔹 **5. Identifying Exploitable Behavior**
Rather than just looking for known security flaws, consider:
- How would a sophisticated attacker exploit these functions together?
- Are there hidden interactions between functions that might not be obvious at first?
- Could a sequence of function calls lead to financial loss, privilege escalation, or contract manipulation?
- Is there a scenario where incorrect function logic could be exploited to alter contract behavior?

**Always check if an attack scenario is realistic and executable in practice.**  
⚠️ **If an issue is purely theoretical and does not lead to tangible risk, do NOT classify it as a vulnerability.**

---

### 🔹 **6. Risk Classification**
#### ✅ **1 - Low Risk (QA & Governance/Centralization)**
- **State handling issues (e.g., function modifies state incorrectly but does not put assets at risk)**
- **Functions that do not work according to spec (e.g., incorrect return values, function logic errors)**
- **Governance & Centralization Risks (e.g., excessive admin privileges, lack of timelocks)**
- **Excludes gas optimizations (which are evaluated separately)**
- **Excludes non-critical issues such as code style, clarity, syntax, and event monitoring**

#### ⚠️ **2 - Medium Risk**
- **Assets are NOT directly at risk, but the protocol’s function or availability could be impacted**
- **Potential for leaking value under specific hypothetical attack conditions**
- **Issues that depend on external conditions or requirements but could become critical under certain circumstances**

#### 🚨 **3 - High Risk**
- **Assets can be stolen, lost, or compromised directly**
- **Indirect exploits that allow asset loss without requiring unrealistic assumptions**
- **Critical financial risk, access control failures, or logical bugs leading to loss of user funds**

---

### 7. Result Output Format
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

---

### 8. Smart Contracts to Audit:
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

### 1️⃣ **Audit Report from Security Analyst**
The following vulnerabilities were initially detected by the security auditor:

{result}

These vulnerabilities were flagged as **potential security risks**, but your role is to **validate whether they are actual threats that could cause real financial or operational damage**.

---

### 1. **Reviewer Objectives**
Your role as a **security reviewer** is to analyze the vulnerabilities from three different perspectives:

- 🔹 **Code Logic Bug:**  
    - Does the function have an internal logic error that causes unintended behavior?
    - Could the code execute incorrectly due to an implementation flaw?

- 🔹 **Business Logic Bug:**  
    - Does the function fail to achieve the intended protocol behavior?
    - Could an attacker **abuse contract functionality** to gain an unfair advantage?
    - Are incentives misaligned, allowing unintended financial gain?

- 🔹 **System Bug:**  
    - Could this vulnerability be exploited in a way that **affects protocol security or stability**?
    - Are external dependencies (oracles, external calls, state updates) causing a critical issue?
    - Could this issue create **network-wide disruptions or systemic risks**?

**🔹  Access Control & Trusted Entity Assumptions**
- Identify any **modifier** or **require statement** that restricts function execution.
- Determine **who is allowed** to execute the function (e.g., `onlyOwner`, `onlyOperator`, `onlyVault`).
- **Use the following trust assumptions for access control:**
    - ✅ **Operators (`onlyOperator`) are trusted and do not act maliciously.**
    - ✅ **Vault-controlled functions (`onlyVault`) are managed by the protocol and are trusted.**
    - ⚠️ **Governance-controlled functions (`onlyGovernance`) depend on the DAO and can be manipulated by governance attacks.**
    - ❌ **Publicly accessible functions (`public`, `external`) should be fully scrutinized for vulnerabilities.**

**If a function is controlled by a trusted entity (e.g., onlyOperator, onlyVault), assume they do not act maliciously and adjust risk classification accordingly.**  

**📌 If the vulnerability is confirmed:**
- Clearly categorize whether it is a **Code Logic Bug, Business Logic Bug, or System Bug**.
- Identify **who can execute the vulnerable function**.
- Determine **if they are trusted** and adjust risk classification accordingly.
- Provide a **detailed issue description** explaining why it is valid.
- Construct a **realistic attack scenario** demonstrating how an exploit could occur (POC).
- Assess the **potential impact on the contract, users, and funds**.
- Suggest a **high-level fix** to mitigate the risk.

**📌 If the vulnerability is a false positive:**
- Explain why the flagged issue **does not** introduce an actual security threat.
- Identify **any misunderstandings** in the original audit that led to this incorrect classification.

---

### 🔹 **2. Risk Classification**
#### ✅ **1 - Low Risk (QA & Governance/Centralization)**
- **State handling issues (e.g., function modifies state incorrectly but does not put assets at risk)**
- **Functions that do not work according to spec (e.g., incorrect return values, function logic errors)**
- **Governance & Centralization Risks (e.g., excessive admin privileges, lack of timelocks)**
- **Excludes gas optimizations (which are evaluated separately)**
- **Excludes non-critical issues such as code style, clarity, syntax, and event monitoring**

#### ⚠️ **2 - Medium Risk**
- **Assets are NOT directly at risk, but the protocol's function or availability could be impacted**
- **Potential for leaking value under specific hypothetical attack conditions**
- **Issues that depend on external conditions or requirements but could become critical under certain circumstances**

#### 🚨 **3 - High Risk**
- **Assets can be stolen, lost, or compromised directly**
- **Indirect exploits that allow asset loss without requiring unrealistic assumptions**
- **Critical financial risk, access control failures, or logical bugs leading to loss of user funds**

---

### 3. **Smart Contract for Review**
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


