import logging
from typing import List, Dict
from core.jira_confluence_connector import AtlassianConnector

logger = logging.getLogger("RAGEngine")

class SimpleRAGEngine:
    """RAG Engine In-Memory kết hợp Mock Data EdTech."""
    def __init__(self):
        self.connector = AtlassianConnector()
        self.documents = []
        self.init_vector_store()

    def get_mock_data(self) -> List[Dict]:
        return [
            {
                "title": "Hồ sơ Học sinh: Bé Min",
                "content": "Bé Min. Hội chứng: ASD nhẹ. Nhạy cảm ánh sáng đỏ và tiếng ồn. Quy tắc: Giảm độ phức tạp UI, dùng màu dịu khi quá tải.",
                "source": "Confluence", "type": "profile"
            },
            {
                "title": "IEP-002: Đếm 6-10",
                "content": "Mục tiêu: Đếm 6-10 con thỏ. Đang thực hiện.",
                "source": "Jira", "type": "task"
            }
        ]

    def init_vector_store(self):
        self.documents.extend(self.connector.fetch_live_confluence_pages())
        self.documents.extend(self.connector.fetch_live_jira_tasks())
        
        if not self.documents:
            logger.info("Using EdTech Mock Data for RAG.")
            self.documents = self.get_mock_data()

    def search(self, query: str, limit: int = 2) -> List[Dict]:
        """Simple keyword matching, luôn fallback mock nếu không có dữ liệu sống hoặc hết dữ liệu."""
        # Nếu documents trống (có thể do mất kết nối sau runtime) -> fallback luôn mock data
        if not self.documents:
            logger.warning("Vector store empty at search time, fallback mock data.")
            self.documents = self.get_mock_data()
            
        query_words = set(query.lower().split())
        scored = []
        for doc in self.documents:
            text = f"{doc.get('title','')} {doc.get('content','')}".lower()
            score = sum(1 for w in query_words if w in text)
            if score > 0:
                scored.append((score, doc))
                
        scored.sort(key=lambda x: x[0], reverse=True)
        result = [d for s, d in scored[:limit]]
        # Fallback luôn mock nếu kết quả tìm vẫn rỗng
        return result if result else self.get_mock_data()[:limit]
