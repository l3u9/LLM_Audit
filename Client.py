from ContractManager import *
from LLMAuditor import *
from Tracer import *
from utils import *

class Client:
    def __init__(self):
        self.manager = ContractManager()
        self.auditor = LLMAuditor(model="deepseek-r1-distill-qwen-32b")
        self.tracer = Tracer(self.manager)
    
    def load_contracts(self, contract_paths):
        self.manager.initial_save(contract_paths)
        self.manager.load_contracts_info()
    
    def analyze_and_review(self, contract_name, function_name, depth, check_impact=False):

        datas, modifieds, modifiers, impacted_function = self.tracer.trace_function_with_depth(contract_name, function_name, depth)


        if check_impact:
            pass
        else:
            impacted_function = None
        
        decision, keywords = self.auditor.decision_vuln(datas, impacted_function)
        print(keywords)
        if "Vulnerable" in decision:
            # keywords가 None이 아닌 경우에만 라인 번호 포함하여 처리
            keywords_str = ""
            for li in keywords:
                for entry in li:
                    if isinstance(entry, tuple):

                        function_info, code_line = entry
                        
                        if isinstance(function_info, list):

                            function_name = function_info[0]
                            keyword = function_info[1] if len(function_info) > 1 else ""
                            if keyword != "":
                                keywords_str += f"{function_name} - {keyword} (Code Line: {code_line})\n"

            result_str = f"Decision: {decision} | Keywords: {keywords_str}"
            print(result_str)

            review = self.auditor.review_vulnerabilities(datas, impacted_function, result_str)
            return review

        else:
            return None
    
    def analyze_all_contracts_and_functions(self, check_impact=False):
        contracts = self.manager.get_contract_names()

        for contract in contracts:
            contract_name = contract
            functions = self.manager.get_contract_info(contract_name)["Functions"]
            for function in functions:
                function_name = function["Function Name"]
                depth = 3
                review = self.analyze_and_review(contract_name, function_name, depth)
                if review:
                    print(f"Contract: {contract_name}, Function: {function_name}")
                    print(review)
                    print("========================================")





def main():
    IManager = ContractManager()
    IAuditor = LLMAuditor()
    ITracer = Tracer(IManager)

    IManager.initial_save(["LiquidRon.sol", "RonHelper.sol", "LiquidProxy.sol", "ValidatorTracker.sol", "Escrow.sol"])
    IManager.load_contracts_info()


    modifiers = IManager.get_all_modifier_function()
    datas, modifieds, modifiers, impacted_function = ITracer.trace_function_with_depth("LiquidRon", "harvest",3)
    # decison, keywords = IAuditor.decision_vuln(datas, modifiers)
    decision, keywords = IAuditor.decision_vuln(datas, impacted_function)



    # formatting_datas(datas)





    if "Vulnerable" in decision:


        if not keywords or keywords == [None]:
            keywords_str = ""
        else:
            keywords_str = ", ".join(keywords)  # 리스트를 문자열로 변환

        # 최종 문자열 결합
        result_str = f"Decision: {decision} | Keywords: {keywords_str}"

        review = IAuditor.review_vulnerabilities(datas, impacted_function, result_str)




if __name__ == "__main__":
    # main()
    client = Client()
    client.load_contracts(["LiquidRon.sol", "RonHelper.sol", "LiquidProxy.sol", "ValidatorTracker.sol", "Escrow.sol"])
    client.analyze_all_contracts_and_functions()
