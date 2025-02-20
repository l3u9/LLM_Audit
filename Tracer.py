from ContractManager import *
from collections import OrderedDict
from copy import deepcopy
import string

class Tracer:
    def __init__(self, contract_manager):
        self.contract_manager = contract_manager

    def _remove_duplicate_values(self, dict1, dict2):
        # dict1의 값 중 dict2에도 있는 값 제거
        for key in dict1:
            dict1[key] = [value for value in dict1[key] if value not in dict2[key]]
        return dict1
    

    def _remove_duplicates_from_list(self, seq):
        """순서를 유지하며 리스트 내 중복 항목 제거 (해시 불가능한 항목도 처리)"""
        new_list = []
        for item in seq:
            if item not in new_list:
                new_list.append(item)
        return new_list

    def _remove_dup(self, dict_data):
        """
        주어진 딕셔너리(dict_data)의 각 key에 해당하는 리스트에서
        중복된 항목을 제거하여 반환합니다.
        """
        for key in dict_data:
            dict_data[key] = self._remove_duplicates_from_list(dict_data[key])
        return dict_data

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

        internal_calls = self.contract_manager.get_functions_internal_calls(contract_name, function_name)
        external_calls = self.contract_manager.get_functions_external_calls(contract_name, function_name)
        view_pure_calls = self.contract_manager.get_functions_view_pure_calls(contract_name, function_name)




        # contract_names = self.contract_manager.get_contract_names()

        contracts_and_functions = OrderedDict()


        contracts_and_functions[contract_name] = [function_name]

        if internal_calls:
            for calls in internal_calls:
                for function_name in calls:
                    function_names = self.contract_manager.get_function_names(contract_name)
                    if function_name in function_names:
                        if contract_name not in contracts_and_functions:
                            contracts_and_functions[contract_name] = []
                        contracts_and_functions[contract_name].append(function_name)

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
                for function_name in view_pure_call:
                    function_names = self.contract_manager.get_function_names(contract_name)
                    if function_name in function_names:
                        if contract_name not in contracts_and_functions:
                            contracts_and_functions[contract_name] = []
                        contracts_and_functions[contract_name].append(function_name)

        _code_dict = OrderedDict()
        _modified_state_vars = OrderedDict()
        _modifiers = OrderedDict()

        _code_dict = self._get_traced_contract_codes(contracts_and_functions)

        _modified_state_vars = self._get_traced_contract_modified_state_vars(contracts_and_functions)

        _modifiers = self._get_traced_contract_modifiers(contracts_and_functions)

        first_key = next(iter(contracts_and_functions))  # OrderedDict의 첫 번째 키 가져오기

        # 첫 번째 키의 리스트에서 첫 번째 값 pop
        if contracts_and_functions[first_key]:  # 리스트가 비어있지 않은 경우만 pop 수행
            contracts_and_functions[first_key].pop(0)

        return _code_dict, contracts_and_functions, _modified_state_vars, _modifiers



    def trace_function_with_depth(self, contract_name, function_name, depth=3):
        datas, dicts, modifieds, modifiers = self.trace_function(contract_name, function_name)


        impacted_functions = OrderedDict()
        _impacted = self.contract_manager.get_impacted_modified_state_vars(modifieds)

        impacted_functions.update(_impacted)
        temp = deepcopy(dicts)

        for i in range(depth - 1):
            ret = {}

            for dic in temp:
                functions = temp[dic]

                for function in functions:
                    _data, _ret, _modified, _modifiers = self.trace_function(dic, function)
                                    
                    # Ensure _data is a dictionary before updating
                    if isinstance(_data, dict):
                        for key, value in _data.items():
                            if key in datas:
                                if isinstance(datas[key], list) and isinstance(value, list):
                                    datas[key].extend(value)
                                elif isinstance(datas[key], dict) and isinstance(value, dict):
                                    datas[key].update(value)
                                else:
                                    pass
                            else:
                                datas[key] = value
                    else:
                        pass

                    modifieds.update(_modified)
                    modifiers.update(_modifiers)

                    _impacted = self.contract_manager.get_impacted_modified_state_vars(modifieds)
                    impacted_functions.update(_impacted)


                    if _ret:
                        for key in _ret:
                            if key in ret:
                                ret[key].extend(_ret[key])
                            else:
                                ret[key] = _ret[key]

            temp = deepcopy(ret)

        modifier_codes = {}
        for modifier in modifiers:
            modifier_code = self.contract_manager.get_modifier_code(modifier, modifiers[modifier])
            if modifier_code is None:
                continue
            modifier_codes[modifier] = modifier_code

        impacted_functions = self._remove_duplicate_values(impacted_functions, datas)
        datas = self._remove_dup(datas)
        return datas, modifieds, modifier_codes, impacted_functions


if __name__ == "__main__":
    contract_paths = ["KeeperProxy.sol", "GmxProxy.sol", "PerpetualVault.sol", "VaultReader.sol"]
    contract_manager = ContractManager()
    contract_manager.initial_save(contract_paths)
    contract_manager.load_contracts_info()

    tracer = Tracer(contract_manager)

    # print(tracer.trace_function("LiquidRon", "redelegateAmount"))
    # datas, dicts = (tracer.trace_function("LiquidRon", "harvest"))

    datas, modifieds, modifier_code, impacted_functions = tracer.trace_function_with_depth("PerpetualVault", "run", 3)

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
