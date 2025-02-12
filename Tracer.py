from ContractManager import *
from collections import OrderedDict
from copy import deepcopy

class Tracer:
    def __init__(self, contract_manager):
        self.contract_manager = contract_manager

    # 중복 제거 함수
    def _remove_duplicate_values(self, target_dict, reference_dict):
        new_dict = OrderedDict()
        
        for key, value_list in target_dict.items():
            if key in reference_dict:
                reference_values = set(map(tuple, reference_dict[key]))  # 비교군을 튜플로 변환하여 집합 생성
                filtered_values = [val for val in value_list if tuple(val) not in reference_values]
                new_dict[key] = filtered_values
            else:
                new_dict[key] = value_list  # 비교 대상에 없으면 그대로 유지
                
        return new_dict


    def _get_traced_contract_codes(self, dicts):
        self.contract_manager.get_contract_names()
        contract_codes = {}
        for contract_name in dicts:

            function_name = dicts[contract_name]


            for function in function_name:

                function_codes = self.contract_manager.get_function_code(contract_name, function)



                if contract_name not in contract_codes:
                    contract_codes[contract_name] = []

                for code in function_codes:
                    contract_codes[contract_name].append(code)                



        return contract_codes
    
    def _get_traced_contract_modified_state_vars(self, dicts):
        contract_modified_state_vars = {}

        for contract_name in dicts:
            function_name = dicts[contract_name]
            for function in function_name:


                modified_state_vars = self.contract_manager.get_functions_modified_state_vars(contract_name, function)

                if contract_name not in contract_modified_state_vars:
                    contract_modified_state_vars[contract_name] = []
                
                for modified in modified_state_vars:
                    contract_modified_state_vars[contract_name].append(modified)


                # contract_modified_state_vars[contract_name] = modified_state_vars

        return contract_modified_state_vars

    def _get_traced_contract_modifiers(self, dicts):
        contract_modifiers = {}
        for contract_name in dicts:
            function_name = dicts[contract_name]
            for function in function_name:
                modifiers = self.contract_manager.get_contract_modifier_functions(contract_name)


                if contract_name not in contract_modifiers:
                    contract_modifiers[contract_name] = []
                
                for modifier in modifiers:
                    contract_modifiers[contract_name].append(modifier)

                # contract_modifiers[contract_name] = modifiers

        return contract_modifiers


    def trace_function(self, contract_name, function_name):

        os.system("echo 'contract_name: " + contract_name + "'" + " > ./test3.txt")
        internal_calls = self.contract_manager.get_functions_internal_calls(contract_name, function_name)
        external_calls = self.contract_manager.get_functions_external_calls(contract_name, function_name)
        view_pure_calls = self.contract_manager.get_functions_view_pure_calls(contract_name, function_name)





        contract_names = self.contract_manager.get_contract_names()

        contracts_and_functions = OrderedDict()


        contracts_and_functions[contract_name] = [function_name]

        if internal_calls:
            for calls in internal_calls:
                for internal_call in calls:
                    for _contract_name in contract_names:
                        


                        _contract_name = _contract_name

                        function_names = self.contract_manager.get_function_names(_contract_name)



                        if internal_call in function_names:
                            if _contract_name not in contracts_and_functions:
                                contracts_and_functions[_contract_name] = []
                            contracts_and_functions[_contract_name].append(internal_call)
                            break

        if external_calls:
            for external_call in external_calls:
                for interface_name in external_call:


                    _contract_name = interface_name[1:] if interface_name[0] == 'I' else interface_name

                    for function_name in external_call[interface_name]:

                        function_names = self.contract_manager.get_function_names(_contract_name)
                        if function_names == None:
                            continue

                        if function_name in function_names:
                            if _contract_name not in contracts_and_functions:
                                contracts_and_functions[_contract_name] = []
                            contracts_and_functions[_contract_name].append(function_name)

        if view_pure_calls:
            for view_pure_call in view_pure_calls:
                for _contract_name in contract_names:
                    _contract_name = _contract_name
                    function_names = self.contract_manager.get_function_names(_contract_name)
                    if view_pure_call in function_names:
                        if _contract_name not in contracts_and_functions:
                            contracts_and_functions[_contract_name] = []
                        contracts_and_functions[_contract_name].append(view_pure_call)
                        break

        _code_dict = OrderedDict()
        _modified_state_vars = OrderedDict()
        _modifiers = OrderedDict()
        # _impacted_functions = OrderedDict()

        _code_dict = self._get_traced_contract_codes(contracts_and_functions)

        _modified_state_vars = self._get_traced_contract_modified_state_vars(contracts_and_functions)




        _modifiers = self._get_traced_contract_modifiers(contracts_and_functions)

        contracts_and_functions.popitem(last=False)


        return _code_dict, contracts_and_functions, _modified_state_vars, _modifiers

    def trace_function_with_depth(self, contract_name, function_name, depth=2):
        datas, dicts, modifieds, modifiers = self.trace_function(contract_name, function_name)

        impacted_functions = OrderedDict()
        _impacted = self.contract_manager.get_impacted_modified_state_vars(modifieds)


        
        impacted_functions.update(_impacted)

        for i in range(depth-1):
            temp = deepcopy(dicts)
            ret = {}

            for dic in temp:
                functions = dicts[dic]
                for function in functions:
                    _data, _ret, _modified, _modifiers = self.trace_function(dic, function)
                    datas.update(_data)
                    modifieds.update(_modified)
                    modifiers.update(_modifiers)
                    _impacted = self.contract_manager.get_impacted_modified_state_vars(modifieds)
                    impacted_functions.update(_impacted)


            try:
                temp = deepcopy(_ret)
            except:
                break
            

        modifier_codes = {}
        for modifier in modifiers:
            modifier_code = self.contract_manager.get_modifier_code(modifier, modifiers[modifier])
            if modifier_code == None:
                continue
            modifier_codes[modifier] = modifier_code


        impacted_functions = self._remove_duplicate_values(impacted_functions, datas)

        
        return datas, modifieds, modifier_codes, impacted_functions

if __name__ == "__main__":
    contract_paths = ["LiquidRon.sol", "RonHelper.sol", "LiquidProxy.sol", "ValidatorTracker.sol", "Escrow.sol"]
    contract_manager = ContractManager()
    contract_manager.initial_save(contract_paths)
    contract_manager.load_contracts_info()

    tracer = Tracer(contract_manager)

    # print(tracer.trace_function("LiquidRon", "redelegateAmount"))
    # datas, dicts = (tracer.trace_function("LiquidRon", "harvest"))

    datas, modifieds, modifier_code, impacted_functions = tracer.trace_function_with_depth("LiquidRon", "harvest", 3)

    print("Code")
    for data in datas:
        print(data)
        for code in datas[data]:
            print("\n".join(code))
        print("\n")

    print("Modified State Variables")
    for modified in modifieds:
        print(modified)
        print(modifieds[modified])
        print("\n")
    
    print("Modifiers")
    for modifier in modifier_code:
        print(modifier)
        print("\n".join(modifier_code[modifier]))

    print("Impacted Functions")
    # print ordered dict

    print("impacted_functions: ", impacted_functions)
    for impacted in impacted_functions:
        print(impacted)
        # print code format
        
        for code in impacted_functions[impacted]:
            print("\n".join(code))
            print("\n")