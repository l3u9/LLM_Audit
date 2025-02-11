import re
import json
import os

def find_function(functions, function_name):
    for function in functions:
        if function_name in function:
            return function
            
def parse_modified_state_vars(function_code, global_variables):
    """
    Extracts modified state variables within a function.
    Filters out local variables and keeps only those present in `global_variables`.
    """
    modified_state_vars = set()  # ✅ 중복 방지 위해 set 사용
    # pattern = r'\b(?:uint\d*|int\d*|address|bool|string|bytes\d*|mapping|struct|enum|function)?\s*\b(\w+)\s*(=|\+=|-=|\*=|/=|%=|\|=|&=|\^=|<<=|>>=|\+\+|--)\s*(\(?.*)'
    pattern = r'\b(?:uint\d*|int\d*|address|bool|string|bytes\d*|mapping|struct|enum|function)?\s*\b(\w+)(?:\[\w+\])?\s*(=|\+=|-=|\*=|/=|%=|\|=|&=|\^=|<<=|>>=|\+\+|--)\s*(\(?.*)'

    match = re.finditer(pattern, function_code)

    for m in match:
        var_name = m.group(1).strip()
        # print("Matched Variable:", var_name)
        if var_name in global_variables:
            modified_state_vars.add(var_name)

    # print("=====================================")
    return list(modified_state_vars)  # ✅ 최종 반환을 list로 변환



def initial_separate(contract_code):
    functions = []
    function = ""
    contract_code = re.sub(r"/\*\*?[\s\S]*?\*/", "", contract_code)

    for line in contract_code.split("\n"):
        if "//" in line:
            continue
            
        if "function" in line or "constructor" in line or "modifier" in line:
            if function:
                functions.append(function)
            function = line + "\n"
        else:
            function += line + "\n"
    functions.append(function)
    
    global_value = extract_structs_and_variables(functions[0])
    contract_name = get_contract_name(functions[0])[-1]
    print("test contract_name: ", contract_name)
    if contract_name == ["UnknownContract"]:
        for function in functions:
            # print(function)
            # print("=====================================")
            contract_name = get_contract_name(function)[-1]
            if contract_name == ['contract']:
                continue

            if contract_name != ["UnknownContract"]:
                break


    return functions, global_value, contract_name

def get_contract_name(contract_code):
    matches = re.findall(r"\b(abstract\s+contract|contract|library|interface)\s+(\w+)", contract_code)
    return [match[1] for match in matches] if matches else ["UnknownContract"]

def extract_structs_and_variables(solidity_code):
    """
    Extracts:
    - Structs
    - Global Variables
    - Imported Contract Names (for filtering later)
    """
    struct_pattern = r"struct\s+(\w+)"
    structs = re.findall(struct_pattern, solidity_code)
    
    variable_pattern = r"(?:mapping\s*\(.*?\)|struct\s+\w+|enum\s+\w+|bytes\d*|string|address|bool|uint\d*|int\d*)\s+(?:public|private|internal|external)?\s*(\w+)"
    variables = re.findall(variable_pattern, solidity_code)

    import_pattern = r'import\s*\{([^}]+)\}\s*from\s*["\'].*?["\'];'  # Matches {Contract1, Contract2} from "..."
    imported_contracts = []
    
    for match in re.findall(import_pattern, solidity_code):
        imported_contracts.extend([c.strip() for c in match.split(",")])  # Extract multiple imports

    return list(set(structs + variables + imported_contracts))  # Convert set to list for JSON serialization



def parse_function_calls(function_code, global_elements):
    """
    Parses a Solidity function's source code to identify:
    - Internal function calls
    - External interface calls
    - View/Pure function calls, excluding control structures, error handling, type casts, structs, events, and imported contract names.
    """
    
    # Initialize result dictionaries
    function_calls = {
        "internal_functions": [],
        "external_interface_calls": {},
        "view_pure_calls": []
    }

    # Regular expressions
    internal_regex = r'\b(_[a-zA-Z0-9_]+)\s*\('
    # interface_regex = r'\b(I[A-Za-z0-9_]+)(?:\([^)]*\))?\s*\.\s*([a-zA-Z0-9_]+)\s*\('
    interface_regex = r'\b([A-Za-z0-9_]+)(?:\([^)]*\))?\s*\.\s*([a-zA-Z0-9_]+)\s*\('
    view_pure_regex = r'\b([a-zA-Z0-9_]+)\s*\('
    function_def_regex = r'^\s*function\s+([a-zA-Z0-9_]+)\s*\('

    # Solidity reserved keywords and special functions
    solidity_keywords = {
        "if", "else", "for", "while", "do", "switch", "case", "default", "break", "continue", "return", "try", "catch", "throw",
        "returns"
    }
    solidity_type_casts = {
        "address", "uint", "uint256", "int", "int256", "bool", "bytes", "bytes32", "string", "payable"
    }
    solidity_error_handling = {
        "revert", "require", "assert"
    }

    # To track detected function names
    detected_functions = set()
    
    for line in function_code:
        line = line.strip()
        
        # Ignore event emits
        if line.startswith("emit ") or " emit " in line:
            continue

        # Ignore error handling functions
        if line.startswith("revert ") or " revert " in line:
            continue

        # Function definition filtering
        function_def_match = re.match(function_def_regex, line)
        if function_def_match:
            detected_functions.add(function_def_match.group(1))
            continue

        # Internal function calls
        internal_matches = re.findall(internal_regex, line)
        function_calls["internal_functions"].extend(internal_matches)
        detected_functions.update(internal_matches)
        
        # External interface calls
        interface_matches = re.finditer(interface_regex, line)
        for match in interface_matches:
            interface_name, function_name = match.groups()
            
            if interface_name not in function_calls["external_interface_calls"]:
                function_calls["external_interface_calls"][interface_name] = []
            function_calls["external_interface_calls"][interface_name].append(function_name)
            
            detected_functions.add(function_name)
            detected_functions.add(interface_name)
        
        # View/Pure function calls
        view_pure_matches = re.findall(view_pure_regex, line)
        for match in view_pure_matches:
            if (
                match not in detected_functions and
                match not in solidity_keywords and
                match not in solidity_type_casts and
                match not in solidity_error_handling and
                match not in global_elements  # Exclude global variables, structs, and imported contracts
            ):  
                function_calls["view_pure_calls"].append(match)

    # Remove duplicates
    function_calls["internal_functions"] = list(set(function_calls["internal_functions"]))
    
    for interface in function_calls["external_interface_calls"]:
        function_calls["external_interface_calls"][interface] = list(set(function_calls["external_interface_calls"][interface]))
        function_calls["view_pure_calls"] = [vp for vp in function_calls["view_pure_calls"] if vp not in function_calls["external_interface_calls"][interface]]

    function_calls["view_pure_calls"] = list(set(function_calls["view_pure_calls"]))

    return function_calls

# def extract_function_name(function_code):
#     """
#     Extracts the function name from the function definition.
#     """
#     function_def_regex = r'^\s*function\s+([a-zA-Z0-9_]+)\s*\('
    
#     for line in function_code:
#         match = re.match(function_def_regex, line.strip())
#         if match:
#             return match.group(1)
    
#     return "UnknownFunction"

# def extract_function_name(function_code):
#     """
#     Extracts the function name from the function or modifier definition.
#     If it's a modifier, it returns "modifier FunctionName".
#     """
#     function_def_regex = r'^\s*(function|modifier)\s+([a-zA-Z0-9_]+)\s*\('
    
#     for line in function_code:
#         match = re.match(function_def_regex, line.strip())
#         if match:
#             keyword, function_name = match.groups()
#             if keyword == "modifier":
#                 return f"modifier {function_name}"
#             return function_name
    
#     return "UnknownFunction"


# def save_to_json(contract_name, global_value, functions):
#     parsed_info = {
#         "Contract Name": contract_name,
#         "Global Variables": list(global_value),  # Convert set to list to avoid JSON serialization error
#         "Functions": []
#     }
    
#     for function in functions:
#         function_lines = [line for line in function.split("\n") if line.strip() != ""]
#         function_name = extract_function_name(function_lines)  # Extract function name
#         function_calls = parse_function_calls(function_lines, global_value)
        

#         parsed_info["Functions"].append({
#             "Function Name": function_name,  # Store function name
#             "Function Code": function_lines,
#             "Modified State Variables": parse_modified_state_vars(function, global_value),
#             "Function Calls": {
#                 "Internal Functions": function_calls["internal_functions"],
#                 "External Interface Calls": function_calls["external_interface_calls"],
#                 "View/Pure Calls": function_calls["view_pure_calls"]
#             }
#         })
#     print("contractname: ", contract_name)
#     with open(f"{contract_name[0]}_info.json", "w") as f:
#         json.dump(parsed_info, f, indent=4)  # JSON serialization error fixed


def extract_function_or_modifier_name(function_code):
    """
    Extracts the function or modifier name.
    Returns a tuple (type, name), where type is either "function" or "modifier".
    """
    function_def_regex = r'^\s*(function|modifier)\s+([a-zA-Z0-9_]+)\s*\('
    
    for line in function_code:
        match = re.match(function_def_regex, line.strip())
        if match:
            return match.groups()  # (type, name)
    
    return None, "UnknownFunction"

def save_to_json(contract_name, global_value, functions):
    parsed_info = {
        "Contract Name": contract_name,
        "Global Variables": list(global_value),  # Convert set to list to avoid JSON serialization error
        "Functions": [],
        "Modifiers": []
    }
    
    for function in functions:
        function_lines = [line for line in function.split("\n") if line.strip() != ""]
        function_type, function_name = extract_function_or_modifier_name(function_lines)  # Extract function/modifier name
        
        function_calls = parse_function_calls(function_lines, global_value)

        # 함수(Function)와 수정자(Modifier)를 분리하여 저장
        if function_type == "function":
            parsed_info["Functions"].append({
                "Function Name": function_name,
                "Function Code": function_lines,
                "Modified State Variables": parse_modified_state_vars(function, global_value),
                "Function Calls": {
                    "Internal Functions": function_calls["internal_functions"],
                    "External Interface Calls": function_calls["external_interface_calls"],
                    "View/Pure Calls": function_calls["view_pure_calls"]
                }
            })
        elif function_type == "modifier":
            parsed_info["Modifiers"].append({
                "Modifier Name": function_name,
                "Modifier Code": function_lines
            })
    
    print("contractname: ", contract_name)
    with open(f"{contract_name}_info.json", "w") as f:
        json.dump(parsed_info, f, indent=4)  # JSON serialization error fixed

        

def load_from_json(contract_name):
    try:
        with open(f"{contract_name}_info.json", "r") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: {contract_name}_info.json 파일을 찾을 수 없습니다.")
        return None


def save_review_report(contract_name, function_name, review_text, save_path=None):
    """
    리뷰 결과를 report_{contract_name}_{function_name}.md 형식으로 저장하는 함수.
    
    :param contract_name: 스마트 컨트랙트 이름
    :param function_name: 함수 이름
    :param review_text: 리뷰 내용 (Markdown 형식)
    :param save_path: 저장할 디렉토리 경로 (None이면 현재 디렉토리에 저장)
    """
    if save_path is None:
        save_path = os.getcwd()  # 저장 경로가 없으면 현재 작업 디렉토리로 설정

    # 파일명 생성
    filename = f"report_{contract_name}_{function_name}.md"
    filepath = os.path.join(save_path, filename)

    try:
        # 파일 저장
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(review_text)
        print(f"📁 Report saved: {filepath}")
        return filepath
    except Exception as e:
        print(f"❌ Error saving report: {e}")
        return None
    


if __name__ == "__main__":
    with open("LiquidRon.sol", "r") as f:
        contract_code = f.read()

    print("Parsing Solidity Code...")
    functions, global_value, contract_name = initial_separate(contract_code)
    
    # Save parsed information to JSON
    save_to_json(contract_name, global_value, functions)
    
    print(f"Contract Name: {contract_name}")
    print(f"Global Variables: {global_value}")
    print(f"Total Functions: {len(functions)}")
    print("\n")
    print("Parsed information has been saved to", f"{contract_name}_info.json")

    # data = load_from_json("LiquidRon")
    # print(data)
