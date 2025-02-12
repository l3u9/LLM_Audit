import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, 
    QLineEdit, QTextEdit, QHBoxLayout, QMessageBox, QFileDialog, 
    QListWidget, QComboBox, QCheckBox
)
from Client import Client
from utils import save_review_report


class SmartContractAnalyzer(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Smart Contract Security Analyzer")
        self.setGeometry(200, 200, 800, 600)

        # 📌 객체 초기화
        self.client = Client()
        self.uploaded_files = []
        self.contract_data = {}
        self.save_path = None  # 📂 보고서 저장 경로 (기본적으로 None)

        # 📌 UI 초기화
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout()

        # 🔹 API IP 설정 레이아웃
        ip_layout = QHBoxLayout()
        self.label_api = QLabel("API IP Address:")
        self.input_api = QLineEdit(self)
        self.input_api.setPlaceholderText("Enter API IP (e.g., localhost)")
        self.button_set_api = QPushButton("Set API", self)
        self.button_set_api.clicked.connect(self.set_api_ip)
        ip_layout.addWidget(self.label_api)
        ip_layout.addWidget(self.input_api)
        ip_layout.addWidget(self.button_set_api)

        # 🔹 컨트랙트 업로드 레이아웃
        self.label_contracts = QLabel("Uploaded Contracts:")
        self.uploaded_contracts = QListWidget(self)
        self.button_upload = QPushButton("Upload Contract Files", self)
        self.button_upload.clicked.connect(self.upload_contract_files)

        # 🔹 컨트랙트 선택 리스트 (QComboBox)
        self.label_contract_select = QLabel("Select Contract:")
        self.contract_select = QComboBox(self)
        self.contract_select.currentIndexChanged.connect(self.update_function_list)

        # 🔹 함수 선택 리스트 (QComboBox)
        self.label_function_select = QLabel("Select Function:")
        self.function_select = QComboBox(self)

        # 🔹 Impact 체크박스 추가 ✅
        self.impact_checkbox = QCheckBox("Enable Impact Analysis", self)
        self.impact_checkbox.setChecked(False)  # 기본값: 체크 해제

        # 🔹 분석 버튼
        self.button_analyze = QPushButton("Analyze Selected Function", self)
        self.button_analyze.clicked.connect(self.analyze_selected_function)

        self.button_analyze_all = QPushButton("Analyze All Contracts", self)
        self.button_analyze_all.clicked.connect(self.analyze_all_contracts)

        # 🔹 결과 표시 창
        self.result_text = QTextEdit(self)
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("Analysis results will be displayed here...")

        # 🔹 보고서 저장 경로 선택 버튼
        self.button_set_save_path = QPushButton("Set Report Save Path")
        self.button_set_save_path.clicked.connect(self.set_save_path)

        # 🔹 레이아웃 추가
        main_layout.addLayout(ip_layout)
        main_layout.addWidget(self.label_contracts)
        main_layout.addWidget(self.uploaded_contracts)
        main_layout.addWidget(self.button_upload)
        main_layout.addWidget(self.label_contract_select)
        main_layout.addWidget(self.contract_select)
        main_layout.addWidget(self.label_function_select)
        main_layout.addWidget(self.function_select)
        main_layout.addWidget(self.impact_checkbox)  # ✅ Impact 체크박스 추가
        main_layout.addWidget(self.button_analyze)
        main_layout.addWidget(self.button_analyze_all)
        main_layout.addWidget(self.button_set_save_path)
        main_layout.addWidget(self.result_text)

        self.setLayout(main_layout)

    def set_api_ip(self):
        """ API IP 주소 설정 """
        api_ip = self.input_api.text().strip()
        if not api_ip:
            QMessageBox.warning(self, "Warning", "Please enter a valid API IP address.")
            return

        try:
            self.client.auditor.set_api_ip(api_ip)
            QMessageBox.information(self, "Success", f"API IP Set to: {api_ip}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to set API IP: {str(e)}")

    # def upload_contract_files(self):
    #     """ 사용자 스마트 컨트랙트 파일 업로드 """
    #     files, _ = QFileDialog.getOpenFileNames(self, "Select Smart Contract Files", "", "Solidity Files (*.sol);;All Files (*)")

    #     if files:
    #         self.uploaded_files.extend(files)  # 파일 리스트 저장
    #         self.uploaded_contracts.clear()
    #         for file in self.uploaded_files:
    #             self.uploaded_contracts.addItem(file)

    #         # 📂 Client를 통해 컨트랙트 로드
    #         self.client.load_contracts(self.uploaded_files)

    #         # 📑 Select Contract 리스트 업데이트
    #         self.update_contract_list()

    #         QMessageBox.information(self, "Success", "Smart contract files uploaded successfully!")
    def upload_contract_files(self):
        """ 사용자 스마트 컨트랙트 파일 업로드 """
        files, _ = QFileDialog.getOpenFileNames(self, "Select Smart Contract Files", "", "Solidity Files (*.sol);;All Files (*)")

        if files:
            self.uploaded_files.extend(files)  # ✅ 기존 리스트에 새로운 파일 추가 (중복 원인)
            self.uploaded_contracts.clear()  # ❌ 여기서는 위젯을 클리어하지만, self.uploaded_files는 초기화되지 않음
            
            for file in self.uploaded_files:  # ⚠️ 이전에 추가한 파일이 계속 유지됨
                self.uploaded_contracts.addItem(file)

            # 📂 Client를 통해 컨트랙트 로드
            self.client.load_contracts(self.uploaded_files)

            # 📑 Select Contract 리스트 업데이트
            self.update_contract_list()

            QMessageBox.information(self, "Success", "Smart contract files uploaded successfully!")


    def update_contract_list(self):
        """ 컨트랙트 선택 리스트 업데이트 """
        self.contract_select.clear()
        contracts = self.client.manager.get_contract_names()
        for contract in contracts:
            print("📑 Contract Name:", contract)
            self.contract_select.addItem(contract)

    def update_function_list(self):
        """ 함수 선택 리스트 업데이트 """
        self.function_select.clear()
        selected_contract = self.contract_select.currentText()
        if selected_contract:
            print(f"📑 Selected Contract: {selected_contract}")
            functions = self.client.manager.get_contract_info(selected_contract)["Functions"]
            for function in functions:
                self.function_select.addItem(function["Function Name"])

    def set_save_path(self):
        """ 📂 보고서 저장 경로 설정 """
        save_path = QFileDialog.getExistingDirectory(self, "Select Directory to Save Reports")
        if save_path:
            self.save_path = save_path
            print(f"📂 Report Save Path Set: {self.save_path}")

    def analyze_selected_function(self):
        """ 선택된 컨트랙트 & 함수 분석 """
        contract_name = self.contract_select.currentText()
        function_name = self.function_select.currentText()
        depth = 3

        if not contract_name or not function_name:
            QMessageBox.warning(self, "Warning", "Please select a contract and function.")
            return

        check_impact = self.impact_checkbox.isChecked()  # ✅ 체크 여부 확인

        self.result_text.setText("🔍 Analyzing... Please wait.")
        os.system("echo 'contract_name: " + contract_name + "'" + " > ./test.txt")
        review = self.client.analyze_and_review(contract_name, function_name, depth, check_impact=check_impact)

        if review:
            self.result_text.setText(f"📑 Contract: {contract_name}, Function: {function_name}\n\n{review}")
            report_path = save_review_report(contract_name, function_name, review, self.save_path)
            if report_path:
                print(f"✅ Report saved at: {report_path}")
        else:
            self.result_text.setText("✅ No vulnerabilities found.")

    def analyze_all_contracts(self):
        """ 모든 컨트랙트의 모든 함수 분석 """
        contracts = self.client.manager.get_contract_names()
        result_text = ""

        check_impact = self.impact_checkbox.isChecked()  # ✅ 체크 여부 확인

        for contract in contracts:
            contract_name = contract
            print("TESTTEST contract_name: ", contract_name)
            functions = self.client.manager.get_contract_info(contract_name)["Functions"]

            for function in functions:
                function_name = function["Function Name"]
                review = self.client.analyze_and_review(contract_name, function_name, 3, check_impact=check_impact)

                if review:
                    save_review_report(contract_name, function_name, review, self.save_path)

                result_text += f"📑 Contract: {contract_name}, Function: {function_name}\n{review}\n{'-' * 50}\n"

        self.result_text.setText(result_text)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SmartContractAnalyzer()
    window.show()
    sys.exit(app.exec_())
