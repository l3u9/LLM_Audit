from utils import *
import os

class ContractManager:
    def __init__(self):
        self.contract_paths = []
        self.contract_names = []
        self.contracts_info = dict()
        # self.initial_save(self.contract_paths)
        # self.load_contracts_info()

    def initial_save(self, contract_paths):
        for contract_path in contract_paths:
            with open(contract_path, "r") as f:
                contract_code = f.read()
            functions, global_value, contract_name = initial_separate(contract_code)
            self.contract_names.append(contract_name)
            save_to_json(contract_name, global_value, functions)

    def load_contracts_info(self):
        for contract_name in self.contract_names:


            self.contracts_info[contract_name] = load_from_json(contract_name)
    
    def get_contract_names(self):
        return self.contract_names
    
    def get_contract_info(self, contract_name):



        return self.contracts_info.get(contract_name, None)

    def _select_contract_function(self, contract_name, function_name):
        contract_info = self.get_contract_info(contract_name)
        if not contract_info:

            return None

        matching_functions = [
            function
            for function in contract_info["Functions"]
            if function["Function Name"] == function_name
        ]

        if not matching_functions:

            return None

        return matching_functions  # 여러 개의 함수 코드가 있을 수 있으므로 리스트로 반환

    def get_function_code(self, contract_name, function_name):
        functions = self._select_contract_function(contract_name, function_name)
        if not functions:
            return None
        
        function_codes = [function["Function Code"] for function in functions]
        return function_codes
    
    def get_functions_dependencies(self, contract_name, function_name):
        functions = self._select_contract_function(contract_name, function_name)
        if not functions:
            return None
        
        function_dependencies = [
            function["Function Calls"]
            for function in functions
        ]
        return function_dependencies

    def get_functions_internal_calls(self, contract_name, function_name):
        functions = self._select_contract_function(contract_name, function_name)
        if not functions:
            return None
        
        # internal_calls = [
        #     function["Function Calls"]["Internal Functions"]
        #     for function in functions
        # ]
        internal_calls = []
        for function in functions:
            internal_calls.append(function["Function Calls"]["Internal Functions"])
        # internal_calls = functions[0]["Function Calls"]["Internal Functions"]
        return internal_calls
    
    def get_functions_external_calls(self, contract_name, function_name):
        functions = self._select_contract_function(contract_name, function_name)
        if not functions:
            return None
        
        # external_calls = [
        #     function["Function Calls"]["External Interface Calls"]
        #     for function in functions
        # ]
        external_calls = []
        for function in functions:
            external_calls.append(function["Function Calls"]["External Interface Calls"])


        # external_calls = functions[0]["Function Calls"]["External Interface Calls"]

        return external_calls
    
    def get_functions_view_pure_calls(self, contract_name, function_name):
        functions = self._select_contract_function(contract_name, function_name)
        if not functions:
            return None
        
        # view_pure_calls = [
        #     function["Function Calls"]["View/Pure Calls"]
        #     for function in functions
        # ]
        view_pure_calls = []
        for function in functions:
            view_pure_calls.append(function["Function Calls"]["View/Pure Calls"])

        return view_pure_calls
    
    def get_functions_modified_state_vars(self, contract_name, function_name):
        functions = self._select_contract_function(contract_name, function_name)
        if not functions:
            return None
        
        # modified_state_vars = [
        #     function["Modified State Variables"]
        #     for function in functions
        # ]

        modified_state_vars = []
        for function in functions:
            modified_state_vars.append(function["Modified State Variables"])

        return modified_state_vars[0]
    
    def get_function_names(self, contract_name):
        contract_info = self.get_contract_info(contract_name)
        if not contract_info:
            return None
        
        function_names = [
            function["Function Name"]
            for function in contract_info["Functions"]
        ]
        return function_names
    
    def get_all_modifier_function(self):
        modifier_functions = []
        for contract_name in self.contract_names:
            contract_name = contract_name
            contract_info = self.get_contract_info(contract_name)
            if not contract_info:
                continue

            for function in contract_info["Modifiers"]:
                if function["Modifier Code"]:
                    modifier_functions.append(function["Modifier Name"])
        

        return modifier_functions
    

    def get_contract_modifier_functions(self, contract_name):
        contract_info = self.get_contract_info(contract_name)
        if not contract_info:
            return None
        
        modifier_functions = [
            function["Modifier Name"]
            for function in contract_info["Modifiers"]
        ]
        return modifier_functions
    
    def get_modifier_code(self, contract_name, modifier_name):
        contract_info = self.get_contract_info(contract_name)
        
        if not contract_info:
            return None
        

        matching_modifiers = [
            modifier
            for modifier in contract_info["Modifiers"]
            if modifier["Modifier Name"] == modifier_name[0]
        ]

        if not matching_modifiers:
            return None
        
        modifier_code = matching_modifiers[0]["Modifier Code"]
        return modifier_code


    def get_impacted_modified_state_vars(self, state_vars):
        # find all contract function that impacted by modified state_vars

        impacted_modified_state_vars = {}

        # output: state_vars:  {'LiquidRon': ['operatorFeeAmount'], 'LiquidProxy': [], 'RonHelper': []}
        for contract_name in state_vars:
            contract_info = self.get_contract_info(contract_name)
            if not contract_info:
                continue

            for state_var in state_vars[contract_name]:
                for function in contract_info["Functions"]:
                    if state_var in function["Modified State Variables"]:
                        if contract_name not in impacted_modified_state_vars:
                            impacted_modified_state_vars[contract_name] = []
                        impacted_modified_state_vars[contract_name].append(function["Function Code"])
        
        return impacted_modified_state_vars



if __name__ == "__main__":
    contract_paths = ["LiquidRon.sol", "RonHelper.sol", "LiquidProxy.sol", "ValidatorTracker.sol", "Escrow.sol"]
    contract_manager = ContractManager()
    contract_manager.initial_save(contract_paths)
    contract_manager.load_contracts_info()

    # 특정 함수 코드 가져오기 예제
    contract_name = "LiquidRon"
    function_name = "harvest"
    function_codes = contract_manager.get_function_code(contract_name, function_name)

    function_dependencies = contract_manager.get_functions_dependencies(contract_name, function_name)

    internal_calls = contract_manager.get_functions_internal_calls(contract_name, function_name)
    external_calls = contract_manager.get_functions_external_calls(contract_name, function_name)
    view_pure_calls = contract_manager.get_functions_view_pure_calls(contract_name, function_name)
    modified_state_vars = contract_manager.get_functions_modified_state_vars(contract_name, function_name)

    impacted_function = contract_manager.get_impacted_modified_state_vars(modified_state_vars)

    

    for impacted in impacted_function:
        print(impacted[0])
        print(impacted[1])
        print("\n")


        

