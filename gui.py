import sys
import os
import traceback
import inspect
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QMessageBox, QFileDialog, QListWidget, QListWidgetItem,
    QComboBox, QCheckBox, QSpinBox, QDoubleSpinBox, QProgressBar, QGroupBox, QSplitter
)
from PyQt5.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot, Qt
from Client import Client
from utils import save_review_report


# WorkerSignals: 작업 완료, 에러, 진행 상태 전달
class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(tuple)
    progress = pyqtSignal(int, int, str)  # (현재 작업, 전체 작업 수, 진행 메시지)


# CancellableWorker: 취소 기능을 포함한 Worker 클래스
class CancellableWorker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    @pyqtSlot()
    def run(self):
        try:
            if "progress_callback" in inspect.getfullargspec(self.fn).args:
                self.kwargs["progress_callback"] = self.signals.progress.emit
            if "is_cancelled" in inspect.getfullargspec(self.fn).args:
                self.kwargs["is_cancelled"] = lambda: self._is_cancelled
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            self.signals.error.emit((e, traceback.format_exc()))
        else:
            self.signals.finished.emit(result)


class SmartContractAnalyzer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Contract Security Analyzer")
        self.resize(1200, 800)

        # 객체 초기화
        self.client = Client()
        self.uploaded_files = []
        self.contract_data = {}
        self.save_path = None
        self.threadpool = QThreadPool()
        self.current_worker = None

        # 선택한 컨트랙트의 순서를 기록하는 리스트
        self.selected_contracts_order = []

        self.initUI()

    def initUI(self):
        # ── 개별 그룹 박스 생성 ──
        # 1. 설정 그룹 (API, Depth, LLM 파라미터)
        settings_group = QGroupBox("설정")
        settings_layout = QGridLayout()
        # API IP 설정
        settings_layout.addWidget(QLabel("API IP Address:"), 0, 0)
        self.input_api = QLineEdit(self)
        self.input_api.setPlaceholderText("Enter API IP (e.g., localhost)")
        settings_layout.addWidget(self.input_api, 0, 1)
        self.button_set_api = QPushButton("Set API", self)
        self.button_set_api.clicked.connect(self.set_api_ip)
        settings_layout.addWidget(self.button_set_api, 0, 2)
        # Analysis Depth
        settings_layout.addWidget(QLabel("Analysis Depth:"), 1, 0)
        self.spinbox_depth = QSpinBox(self)
        self.spinbox_depth.setMinimum(1)
        self.spinbox_depth.setMaximum(100)
        self.spinbox_depth.setValue(2)
        settings_layout.addWidget(self.spinbox_depth, 1, 1)
        # LLM Parameter Settings (별도 그룹으로 구성)
        llm_group = QGroupBox("LLM Parameter Settings")
        llm_layout = QGridLayout()
        llm_layout.addWidget(QLabel("Context Length (Max Tokens):"), 0, 0)
        self.spinbox_context_length = QSpinBox(self)
        self.spinbox_context_length.setMinimum(1)
        self.spinbox_context_length.setMaximum(100000)
        self.spinbox_context_length.setValue(50000)
        llm_layout.addWidget(self.spinbox_context_length, 0, 1)
        llm_layout.addWidget(QLabel("Temperature:"), 1, 0)
        self.spinbox_temperature = QDoubleSpinBox(self)
        self.spinbox_temperature.setDecimals(2)
        self.spinbox_temperature.setMinimum(0.0)
        self.spinbox_temperature.setMaximum(1.0)
        self.spinbox_temperature.setSingleStep(0.1)
        self.spinbox_temperature.setValue(0.8)
        llm_layout.addWidget(self.spinbox_temperature, 1, 1)
        llm_layout.addWidget(QLabel("Top_p:"), 2, 0)
        self.spinbox_top_p = QDoubleSpinBox(self)
        self.spinbox_top_p.setDecimals(2)
        self.spinbox_top_p.setMinimum(0.0)
        self.spinbox_top_p.setMaximum(1.0)
        self.spinbox_top_p.setSingleStep(0.1)
        self.spinbox_top_p.setValue(0.5)
        llm_layout.addWidget(self.spinbox_top_p, 2, 1)
        llm_layout.addWidget(QLabel("Number of Samples:"), 3, 0)
        self.spinbox_num_samples = QSpinBox(self)
        self.spinbox_num_samples.setMinimum(1)
        self.spinbox_num_samples.setMaximum(10)
        self.spinbox_num_samples.setValue(5)
        llm_layout.addWidget(self.spinbox_num_samples, 3, 1)
        self.button_apply_llm_settings = QPushButton("Apply LLM Settings", self)
        self.button_apply_llm_settings.clicked.connect(self.apply_llm_settings)
        llm_layout.addWidget(self.button_apply_llm_settings, 4, 0, 1, 2)
        llm_group.setLayout(llm_layout)
        settings_layout.addWidget(llm_group, 2, 0, 1, 3)
        settings_group.setLayout(settings_layout)

        # 2. 파일 업로드 그룹
        upload_group = QGroupBox("컨트랙트 파일 업로드")
        upload_layout = QVBoxLayout()
        self.uploaded_contracts = QListWidget(self)
        upload_layout.addWidget(QLabel("Uploaded Contracts:"))
        upload_layout.addWidget(self.uploaded_contracts)
        self.button_upload = QPushButton("Upload Contract Files", self)
        self.button_upload.clicked.connect(self.upload_contract_files)
        upload_layout.addWidget(self.button_upload)
        self.button_upload_folder = QPushButton("Upload Contract Folder", self)
        self.button_upload_folder.clicked.connect(self.upload_contract_folder)
        upload_layout.addWidget(self.button_upload_folder)
        upload_group.setLayout(upload_layout)

        # 3. 컨트랙트 및 함수 선택 그룹
        selection_group = QGroupBox("컨트랙트 및 함수 선택")
        selection_layout = QHBoxLayout()
        # 좌측: 컨트랙트 체크리스트 (체크한 순서를 기록)
        left_select_layout = QVBoxLayout()
        self.contract_checklist = QListWidget(self)
        self.contract_checklist.setSelectionMode(QListWidget.NoSelection)
        self.contract_checklist.itemChanged.connect(self.on_contract_selection_changed)
        left_select_layout.addWidget(QLabel("Select Contracts:"))
        left_select_layout.addWidget(self.contract_checklist)
        # 우측: 단일 컨트랙트 선택 시 함수 선택
        right_select_layout = QVBoxLayout()
        self.function_select = QComboBox(self)
        self.function_select.setEnabled(False)
        right_select_layout.addWidget(QLabel("Select Function:"))
        right_select_layout.addWidget(self.function_select)
        selection_layout.addLayout(left_select_layout)
        selection_layout.addLayout(right_select_layout)
        selection_group.setLayout(selection_layout)

        # 4. 분석 실행 그룹
        analysis_group = QGroupBox("분석 실행")
        analysis_layout = QVBoxLayout()
        self.impact_checkbox = QCheckBox("Enable Impact Analysis", self)
        self.impact_checkbox.setChecked(False)
        analysis_layout.addWidget(self.impact_checkbox)
        self.button_analyze = QPushButton("Analyze Selected Function", self)
        self.button_analyze.clicked.connect(self.analyze_selected_function)
        analysis_layout.addWidget(self.button_analyze)
        self.button_analyze_selected_contracts = QPushButton("Analyze All Functions in Selected Contracts", self)
        self.button_analyze_selected_contracts.clicked.connect(self.analyze_all_functions_in_selected_contracts)
        analysis_layout.addWidget(self.button_analyze_selected_contracts)
        self.button_analyze_all = QPushButton("Analyze All Contracts", self)
        self.button_analyze_all.clicked.connect(self.analyze_all_contracts)
        analysis_layout.addWidget(self.button_analyze_all)
        analysis_group.setLayout(analysis_layout)

        # ── 전체 레이아웃 재배치 (좌우 분할 + 하단 결과 영역) ──
        main_layout = QVBoxLayout()
        # 상단: 좌측에는 설정과 파일 업로드, 우측에는 컨트랙트 선택 및 분석 실행
        top_splitter = QSplitter(Qt.Horizontal)
        left_panel = QWidget()
        left_panel_layout = QVBoxLayout()
        left_panel_layout.addWidget(settings_group)
        left_panel_layout.addWidget(upload_group)
        left_panel.setLayout(left_panel_layout)
        right_panel = QWidget()
        right_panel_layout = QVBoxLayout()
        right_panel_layout.addWidget(selection_group)
        right_panel_layout.addWidget(analysis_group)
        right_panel.setLayout(right_panel_layout)
        top_splitter.addWidget(left_panel)
        top_splitter.addWidget(right_panel)
        top_splitter.setSizes([600, 600])
        main_layout.addWidget(top_splitter)

        # 하단: 결과 텍스트와 진행 상태 표시
        self.result_text = QTextEdit(self)
        self.result_text.setReadOnly(True)
        self.result_text.setPlaceholderText("Analysis results will be displayed here...")
        main_layout.addWidget(self.result_text)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        main_layout.addWidget(self.progress_bar)
        self.progress_label = QLabel("진행 상태: 대기중", self)
        main_layout.addWidget(self.progress_label)
        self.button_cancel = QPushButton("Cancel Current Task", self)
        self.button_cancel.clicked.connect(self.cancel_current_task)
        main_layout.addWidget(self.button_cancel)

        self.setLayout(main_layout)

    # ── 기능 메서드 ──

    def set_api_ip(self):
        api_ip = self.input_api.text().strip()
        if not api_ip:
            QMessageBox.warning(self, "Warning", "Please enter a valid API IP address.")
            return
        try:
            self.client.auditor.set_api_ip(api_ip)
            QMessageBox.information(self, "Success", f"API IP Set to: {api_ip}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to set API IP: {str(e)}")

    def apply_llm_settings(self):
        context_length = self.spinbox_context_length.value()
        temperature = self.spinbox_temperature.value()
        top_p = self.spinbox_top_p.value()
        num_samples = self.spinbox_num_samples.value()
        try:
            self.client.auditor.set_context_length(context_length)
            self.client.auditor.set_temperature(temperature)
            self.client.auditor.set_top_p(top_p)
            self.client.auditor.set_num_samples(num_samples)
            QMessageBox.information(self, "Success", "LLM settings applied successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply LLM settings: {str(e)}")

    def upload_contract_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Smart Contract Files", "", "Solidity Files (*.sol);;All Files (*)")
        if files:
            self.uploaded_files = files
            self.uploaded_contracts.clear()
            for file in self.uploaded_files:
                self.uploaded_contracts.addItem(file)
            self.client.load_contracts(self.uploaded_files)
            self.update_contract_list()
            QMessageBox.information(self, "Success", "Smart contract files uploaded successfully!")

    def upload_contract_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder Containing Contracts")
        if folder:
            contract_files = []
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.endswith(".sol"):
                        contract_files.append(os.path.join(root, file))
            if contract_files:
                self.uploaded_files = contract_files
                self.uploaded_contracts.clear()
                for file in contract_files:
                    self.uploaded_contracts.addItem(file)
                self.client.load_contracts(contract_files)
                self.update_contract_list()
                QMessageBox.information(self, "Success", "모든 스마트 컨트랙트 파일이 성공적으로 업로드되었습니다!")
            else:
                QMessageBox.warning(self, "Warning", "선택한 폴더 내에 Solidity 파일이 없습니다.")

    def update_contract_list(self):
        self.contract_checklist.clear()
        contracts = self.client.manager.get_contract_names()
        for contract in contracts:
            item = QListWidgetItem(contract)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            # 이미 사용자가 선택한 컨트랙트라면 체크 상태 유지
            if contract in self.selected_contracts_order:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.contract_checklist.addItem(item)

    def on_contract_selection_changed(self, item):
        contract = item.text()
        # 체크하면 선택 순서에 추가, 체크 해제하면 제거
        if item.checkState() == Qt.Checked:
            if contract not in self.selected_contracts_order:
                self.selected_contracts_order.append(contract)
        else:
            if contract in self.selected_contracts_order:
                self.selected_contracts_order.remove(contract)
        # 단일 컨트랙트 선택 시 함수 선택 콤보박스 활성화
        if len(self.selected_contracts_order) == 1:
            self.function_select.setEnabled(True)
            self.update_function_list()
        else:
            self.function_select.clear()
            self.function_select.setEnabled(False)

    def get_selected_contracts(self):
        # 사용자가 체크한 순서대로 컨트랙트를 반환
        return self.selected_contracts_order

    def update_function_list(self):
        self.function_select.clear()
        selected_contracts = self.get_selected_contracts()
        if len(selected_contracts) == 1:
            contract = selected_contracts[0]
            functions = self.client.manager.get_contract_info(contract)["Functions"]
            for function in functions:
                self.function_select.addItem(function["Function Name"])

    def analyze_selected_function(self):
        selected_contracts = self.get_selected_contracts()
        if len(selected_contracts) != 1:
            QMessageBox.warning(self, "Warning", "단일 함수 분석은 정확히 1개의 컨트랙트를 선택해야 합니다.")
            return
        self.result_text.setText("🔍 Analyzing... Please wait.")
        # _analyze_selected_function 함수를 worker로 실행
        worker = CancellableWorker(self._analyze_selected_function)
        self.current_worker = worker
        worker.signals.finished.connect(self.handle_analyze_selected_function_result)
        worker.signals.error.connect(self.handle_worker_error)
        self.threadpool.start(worker)

    def _analyze_selected_function(self, progress_callback, is_cancelled):
        # 단일 함수 분석에 대한 처리
        selected_contracts = self.get_selected_contracts()
        contract_name = selected_contracts[0]
        function_name = self.function_select.currentText()
        depth = self.spinbox_depth.value()
        check_impact = self.impact_checkbox.isChecked()
        
        # 진행 상황 업데이트 (단일 작업이므로 1/1로 처리)
        progress_callback(1, 1, f"Analyzing {contract_name}::{function_name}")
        
        # 분석 실행
        review = self.client.analyze_and_review(contract_name, function_name, depth, check_impact=check_impact)
        if review:
            report_path = save_review_report(contract_name, function_name, review, self.save_path)
            if report_path:
                print(f"✅ Report saved at: {report_path}")
        else:
            review = "✅ No vulnerabilities found."
        
        return f"📑 Contract: {contract_name}, Function: {function_name}\n\n{review}"

    def handle_analyze_selected_function_result(self, result_text):
        self.current_worker = None
        self.result_text.setText(result_text)

    def analyze_all_contracts(self):
        self.result_text.setText("🔍 Analyzing all contracts... Please wait.")
        worker = CancellableWorker(self._analyze_all_contracts)
        self.current_worker = worker
        worker.signals.progress.connect(self.update_progress)
        worker.signals.finished.connect(self.handle_analyze_all_contracts_result)
        worker.signals.error.connect(self.handle_worker_error)
        self.threadpool.start(worker)

    def _analyze_all_contracts(self, progress_callback, is_cancelled):
        contracts = self.client.manager.get_contract_names()
        total = sum(len(self.client.manager.get_contract_info(contract)["Functions"]) for contract in contracts)
        current = 0
        result_text = ""
        depth = self.spinbox_depth.value()
        check_impact = self.impact_checkbox.isChecked()
        for contract in contracts:
            functions = self.client.manager.get_contract_info(contract)["Functions"]
            for function in functions:
                if is_cancelled():
                    return "작업이 취소되었습니다."
                current += 1
                function_name = function["Function Name"]
                progress_callback(current, total, f"Analyzing {contract}::{function_name} ({current}/{total})")
                review = self.client.analyze_and_review(contract, function_name, depth, check_impact=check_impact)
                if review:
                    report_path = save_review_report(contract, function_name, review, self.save_path)
                    if report_path:
                        print(f"✅ Report saved at: {report_path}")
                else:
                    review = "✅ No vulnerabilities found."
                result_text += f"📑 Contract: {contract}, Function: {function_name}\n{review}\n{'-' * 50}\n"
        return result_text

    def handle_analyze_all_contracts_result(self, result_text):
        self.current_worker = None
        self.result_text.setText(result_text)
        self.progress_bar.setValue(100)
        self.progress_label.setText("분석 완료")

    def analyze_all_functions_in_selected_contracts(self):
        selected_contracts = self.get_selected_contracts()
        if not selected_contracts:
            QMessageBox.warning(self, "Warning", "분석할 컨트랙트를 최소 1개 이상 선택해 주세요.")
            return
        self.result_text.setText("🔍 Analyzing functions in selected contracts... Please wait.")
        worker = CancellableWorker(self._analyze_all_functions_in_selected_contracts, selected_contracts)
        self.current_worker = worker
        worker.signals.progress.connect(self.update_progress)
        worker.signals.finished.connect(self.handle_analyze_all_functions_in_selected_contracts_result)
        worker.signals.error.connect(self.handle_worker_error)
        self.threadpool.start(worker)

    def _analyze_all_functions_in_selected_contracts(self, selected_contracts, progress_callback, is_cancelled):
        total = sum(len(self.client.manager.get_contract_info(contract)["Functions"]) for contract in selected_contracts)
        current = 0
        result_text = ""
        depth = self.spinbox_depth.value()
        check_impact = self.impact_checkbox.isChecked()
        for contract in selected_contracts:
            result_text += f"📑 Contract: {contract}\n\n"
            functions = self.client.manager.get_contract_info(contract)["Functions"]
            for function in functions:
                if is_cancelled():
                    return "작업이 취소되었습니다."
                current += 1
                function_name = function["Function Name"]
                progress_callback(current, total, f"Analyzing {contract}::{function_name} ({current}/{total})")
                review = self.client.analyze_and_review(contract, function_name, depth, check_impact=check_impact)
                if review:
                    report_path = save_review_report(contract, function_name, review, self.save_path)
                    if report_path:
                        print(f"✅ Report saved at: {report_path}")
                else:
                    review = "✅ No vulnerabilities found."
                result_text += f"🔍 Function: {function_name}\n{review}\n{'-' * 50}\n"
            result_text += "\n"
        return result_text

    def handle_analyze_all_functions_in_selected_contracts_result(self, result_text):
        self.current_worker = None
        self.result_text.setText(result_text)
        self.progress_bar.setValue(100)
        self.progress_label.setText("분석 완료")

    @pyqtSlot(int, int, str)
    def update_progress(self, current, total, message):
        percentage = int((current / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(percentage)
        self.progress_label.setText(message)

    def cancel_current_task(self):
        if self.current_worker is not None:
            self.current_worker.cancel()
            self.progress_label.setText("작업 취소 요청됨")
            self.current_worker = None

    def handle_worker_error(self, error_info):
        self.current_worker = None
        e, tb = error_info
        QMessageBox.critical(self, "Error", f"An error occurred:\n{str(e)}\n\n{tb}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SmartContractAnalyzer()
    window.show()
    sys.exit(app.exec_())
