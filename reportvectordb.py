import os
import re
from chromadb import Client
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
'''intfloat/multilingual-e5-small
microsoft/codebert-base
'''
class ReportVectorDB:
    def __init__(self, reports_dir="reports", collection_name="code4rena_findings", embedding_model="intfloat/multilingual-e5-small", chunk_size=500):
        """벡터 DB 초기화"""
        self.reports_dir = reports_dir
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.chunk_size = chunk_size
        self.chroma_client = Client(Settings(persist_directory="./chroma_db", is_persistent=True))
        self.model = SentenceTransformer(self.embedding_model)
        self.collection = self.chroma_client.get_or_create_collection(name=self.collection_name)

    def chunk_document(self, document):
        """문서를 청크로 나누기"""
        chunks = []
        for i in range(0, len(document), self.chunk_size):
            chunk = document[i:i + self.chunk_size]
            chunks.append(chunk)
        return chunks

    def extract_findings(self, content, filename):
        """리포트에서 High/Medium 취약점 보고서 추출"""
        documents = []
        metadatas = []
        ids = []

        # 간단한 구조 검증 (프론트매터와 본문 분리)
        frontmatter_pattern = r"^---\n(.*?)\n---\n(.*)$"
        match = re.match(frontmatter_pattern, content, re.DOTALL)
        if not match:
            print(f"파일 '{filename}'에 프론트매터가 없습니다. 무시됩니다.")
            return [], [], []
        _, body = match.groups()

        # High/Medium 취약점만 추출
        finding_pattern = r"(## \[\[(H|M)-\d+\].*?(?=\n## \[|$))"
        matches = re.findall(finding_pattern, body, re.DOTALL)

        if not matches:
            print(f"파일 '{filename}'에 High/Medium 취약점 보고서가 없습니다. 무시됩니다.")
            return [], [], []

        for i, match in enumerate(matches):
            finding = match[0]  # 전체 매치 문자열
            finding_id = f"{filename.replace('.md', '')}_finding_{i+1}"
            finding_type_match = re.match(r"## \[\[(H|M)-\d+\].*?\)", finding)
            finding_type = finding_type_match.group(0) if finding_type_match else "N/A"
            documents.append(finding.strip())
            metadatas.append({
                "filename": filename,
                "source": os.path.join(self.reports_dir, filename),
                "finding_id": finding_id,
                "finding_type": finding_type
            })
            ids.append(finding_id)

        return documents, metadatas, ids

    def load_reports(self):
        """reports 폴더에서 .md 파일 로드, 청킹하여 준비"""
        documents = []
        metadatas = []
        ids = []

        for filename in os.listdir(self.reports_dir):
            if filename.endswith(".md"):
                file_path = os.path.join(self.reports_dir, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                file_docs, file_metas, file_ids = self.extract_findings(content, filename)
                for doc, meta, fid in zip(file_docs, file_metas, file_ids):
                    chunks = self.chunk_document(doc)
                    for j, chunk in enumerate(chunks):
                        chunk_id = f"{fid}_chunk_{j+1}"
                        documents.append(chunk)
                        metadatas.append({**meta, "chunk_id": j+1})
                        ids.append(chunk_id)

        return documents, metadatas, ids

    def store_to_vector_db(self, batch_size=10000):
        """Store reports into the vector DB with batch size limiting."""
        # Load the documents, metadata, and IDs
        documents, metadatas, ids = self.load_reports()
        
        # Check if there’s anything to store
        if not documents:
            print("No chunks to store.")
            return
        
        # Convert documents to embeddings
        print("Converting documents to vectors...")
        embeddings = self.model.encode(documents, show_progress_bar=True)
        
        # Get total number of items
        total = len(documents)
        
        # Process data in batches
        for i in range(0, total, batch_size):
            end = min(i + batch_size, total)
            batch_documents = documents[i:end]
            batch_embeddings = embeddings[i:end]
            batch_metadatas = metadatas[i:end]
            batch_ids = ids[i:end]
            
            # Add the current batch to Chroma DB
            self.collection.add(
                documents=batch_documents,
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
                ids=batch_ids
            )
            print(f"Stored {end}/{total} chunks into the vector DB.")
        
        print("All chunks have been stored in the vector DB.")
        print("Vector DB storage path: ./chroma_db")

    # def query(self, query_text, metadata_filter=None, n_results=10):
    #     """벡터 DB에서 검색 (메타데이터 필터링 적용)"""
    #     query_embedding = self.model.encode([query_text])[0]
    #     results = self.collection.query(
    #         query_embeddings=[query_embedding],
    #         where=metadata_filter,  # 메타데이터 필터 적용
    #         n_results=n_results
    #     )
        
    #     # 결과를 그룹화하여 보고서 단위로 정리
    #     grouped_results = {}
    #     for doc, metadata, distance in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
    #         finding_id = metadata["finding_id"]
    #         if finding_id not in grouped_results:
    #             grouped_results[finding_id] = {
    #                 "filename": metadata["filename"],
    #                 "finding_type": metadata["finding_type"],
    #                 "chunks": [],
    #                 "similarity": 1 - distance
    #             }
    #         grouped_results[finding_id]["chunks"].append({
    #             "content": doc,
    #             "chunk_id": metadata["chunk_id"],
    #             "similarity": 1 - distance
    #         })
        
    #     # 결과 출력
    #     print("검색 결과 (그룹화됨):")
    #     for i, (finding_id, data) in enumerate(grouped_results.items()):
    #         print(f"{i+1}. 파일: {data['filename']}, 보고서: {finding_id} ({data['finding_type']})")
    #         print(f"   청크 수: {len(data['chunks'])}, 평균 유사도: {sum(c['similarity'] for c in data['chunks']) / len(data['chunks']):.4f}")
    #         for chunk in data["chunks"]:
    #             print(f"   - 청크 {chunk['chunk_id']}: 유사도 {chunk['similarity']:.4f}, 내용 미리보기: {chunk['content']}")
        
    #     return grouped_results

    def query(self, query_text, metadata_filter=None, n_results=10, min_similarity=0.0):
        query_embedding = self.model.encode([query_text])[0]
        results = self.collection.query(
            query_embeddings=[query_embedding],
            where=metadata_filter,
            n_results=n_results
        )
        
        print("검색 결과 (그룹화됨):")
        grouped_results = {}
        for doc, metadata, distance in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
            similarity = 1 - distance
            if similarity < min_similarity:  # 임계값 미만 제외
                continue
            finding_id = metadata["finding_id"]
            if finding_id not in grouped_results:
                grouped_results[finding_id] = {
                    "filename": metadata["filename"],
                    "finding_type": metadata["finding_type"],
                    "chunks": [],
                    "similarity": similarity
                }
            grouped_results[finding_id]["chunks"].append({
                "content": doc,
                "chunk_id": metadata["chunk_id"],
                "similarity": similarity
            })
        
        # for i, (finding_id, data) in enumerate(grouped_results.items()):
        #     print(f"{i+1}. 파일: {data['filename']}, 보고서: {finding_id} ({data['finding_type']}), 유사도: {data['similarity']:.4f}")
        #     for chunk in data["chunks"]:
        #         print(f"   - 청크 {chunk['chunk_id']}: 내용: {chunk['content']}")
        
        return grouped_results
    
    def structure_to_string(self, grouped_results):
        """
        Convert the dictionary-formatted query results into a natural, English text format suitable for an LLM prompt.
        
        Args:
            grouped_results (dict): Query result dictionary
        
        Returns:
            str: Text formatted for insertion into an LLM prompt
        """
        prompt_data = "### Reference Data from Past Audits\n\n"
        
        for i, (finding_id, data) in enumerate(grouped_results.items(), 1):
            # Add the finding title and similarity score in a natural sentence
            prompt_data += f"{i}. Finding: {data['finding_type']} (Similarity: {data['similarity']:.4f})\n"
            
            # Process each chunk naturally without "청크" or "내용" labels
            for chunk in data['chunks']:
                prompt_data += f"  This finding from {data['filename']} includes the following details:\n{chunk['content']}\n\n"
        
        return prompt_data

if __name__ == "__main__":
    # 인스턴스 생성
    vector_db = ReportVectorDB(reports_dir="reports", chunk_size=5000)

    # # 리포트 저장 (청킹 적용)
    # print("### 리포트 저장 ###")
    # vector_db.store_to_vector_db()

# 인스턴스 생성
    # vector_db = ReportVectorDB(reports_dir="reports", chunk_size=5000)

    # 검색 테스트
    print("\n### 검색 테스트: 재진입 공격 ###")
    reentrancy_query = """
    function _rebalanceLiquidity() internal {
        // if curve vault is not set, do nothing
        if (address(curveVault) == address(0)) {
            return;
        }

        uint256 totalDeposits = reserve.totalLiquidity; // Total liquidity in the system
        uint256 desiredBuffer = totalDeposits.percentMul(liquidityBufferRatio);
        uint256 currentBuffer = IERC20(reserve.reserveAssetAddress).balanceOf(reserve.reserveRTokenAddress);

        if (currentBuffer > desiredBuffer) {
            uint256 excess = currentBuffer - desiredBuffer;
            // Deposit excess into the Curve vault
            _depositIntoVault(excess);
        } else if (currentBuffer < desiredBuffer) {
            uint256 shortage = desiredBuffer - currentBuffer;
            // Withdraw shortage from the Curve vault
            _withdrawFromVault(shortage);
        }

        emit LiquidityRebalanced(currentBuffer, totalVaultDeposits);
    }


    function deposit(uint256 amount) external nonReentrant whenNotPaused onlyValidAmount(amount) {
        // Update the reserve state before the deposit
        ReserveLibrary.updateReserveState(reserve, rateData);

        // Perform the deposit through ReserveLibrary
        uint256 mintedAmount = ReserveLibrary.deposit(reserve, rateData, amount, msg.sender);

        // Rebalance liquidity after deposit
        _rebalanceLiquidity();

        emit Deposit(msg.sender, amount, mintedAmount);
    }
    """
    prompt_data = vector_db.query(reentrancy_query, n_results=3)
    prompt_data = vector_db.structure_to_string(prompt_data)
    # LLM 프롬프트 생성
    llm_prompt = f"""
    ### Smart Contracts to Audit:
    {reentrancy_query}
    
    {prompt_data}
    """
    print("=====================================")
    print(llm_prompt)