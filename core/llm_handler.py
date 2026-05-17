import os
import json
import time
import logging
import requests

# Khởi tạo cấu hình logging chuẩn để đẩy log trực tiếp lên Render không qua buffer
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LLMHandler")

class LLMHandler:
    """
    Xử lý gọi mô hình ngôn ngữ lớn (gemini-3-flash-preview) bằng API trực tiếp.
    Sử dụng logging hệ thống thay thế print() để hiển thị log tức thì trên Render.
    Tích hợp cơ chế thử lại lũy thừa (Exponential Backoff) khi gặp lỗi mạng.
    """
    def __init__(self):
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.model_name = "gemini-2.5-flash-lite"
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"

    def get_system_prompt(self) -> str:
        return (
            "Bạn là Sếp Park (Park Ji-hoon), Giám đốc điều hành người Hàn Quốc của công ty KTC tại Việt Nam.\n"
            "Tính cách của bạn: Nghiêm túc, đòi hỏi cao trong công việc nhưng rất quan tâm đến cấp dưới (đặc trưng văn hóa Nunchi).\n"
            "Cách giao tiếp: Thỉnh thoảng chêm một vài từ tiếng Hàn phổ biến (Bogo, Gyeoljae, Hoesik, Ne, Kamsahamnida) để giữ bản sắc, "
            "nhưng câu trả lời chính phải bằng tiếng Việt dễ hiểu, mạch lạc.\n"
            "Nhiệm vụ: Trả lời câu hỏi của nhân viên mới dựa trên ngữ cảnh công ty được cung cấp. Tuyệt đối không bịa đặt thông tin nằm ngoài ngữ cảnh.\n"
            "Bạn bắt buộc phải trả về dữ liệu đúng cấu trúc JSON được yêu cầu."
        )

    def generate_response(self, user_query: str, retrieved_context: list[dict]) -> dict:
        if not self.api_key:
            logger.warning("⚠️ Chưa cấu hình LLM_API_KEY trong biến môi trường!")
            return {
                "response_vi": "Chào cậu, hiện tại hệ thống AI của sếp đang bảo trì do thiếu API Key. Cậu vui lòng liên hệ HR hỗ trợ nhé!",
                "korean_terms_explained": {},
                "escalate": False,
                "confidence": 0.0
            }

        # Tạo prompt gộp ngữ cảnh RAG
        context_str = "\n".join([f"- {doc['title']} (Nguồn: {doc['source']}): {doc['content']}" for doc in retrieved_context])
        prompt_text = (
            f"Ngữ cảnh tài liệu công ty:\n{context_str}\n\n"
            f"Câu hỏi của nhân viên: \"{user_query}\"\n\n"
            "Hãy phân tích và trả lời với tư cách Sếp Park dưới định dạng JSON."
        )

        # Định nghĩa cấu trúc JSON đầu ra bắt buộc cho Gemini
        payload = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }],
            "systemInstruction": {
                "parts": [{"text": self.get_system_prompt()}]
            },
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "response_vi": {
                            "type": "STRING",
                            "description": "Câu trả lời bằng tiếng Việt của sếp Park, có chêm từ tiếng Hàn."
                        },
                        "korean_terms_explained": {
                            "type": "OBJECT",
                            "description": "Giải thích các từ tiếng Hàn vừa dùng trong câu trả lời (Key: từ tiếng Hàn, Value: nghĩa tiếng Việt)."
                        },
                        "escalate": {
                            "type": "BOOLEAN",
                            "description": "Đặt thành true nếu câu hỏi của nhân viên thể hiện sự mệt mỏi, bế tắc, áp lực cao, hoặc muốn nghỉ việc."
                        },
                        "confidence": {
                            "type": "NUMBER",
                            "description": "Mức độ tự tin của câu trả lời dựa trên tài liệu được cung cấp (từ 0.0 đến 1.0)."
                        }
                    },
                    "required": ["response_vi", "korean_terms_explained", "escalate", "confidence"]
                }
            }
        }

        # Cơ chế Exponential Backoff để thử lại tối đa 5 lần
        delay = 1.0
        for attempt in range(5):
            try:
                logger.info(f"🔑 Đang gửi yêu cầu tới Gemini API ({self.model_name}) - Lần thử {attempt + 1}...")
                response = requests.post(self.endpoint, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
                
                if response.status_code == 200:
                    result = response.json()
                    raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
                    logger.info("✅ Nhận phản hồi thành công từ Gemini API!")
                    return json.loads(raw_text)
                
                # Ghi nhận log lỗi chi tiết ngay lập tức lên bảng điều khiển Render
                logger.error(f"❌ Gemini API trả về lỗi HTTP {response.status_code}: {response.text}")
                
                # Nếu dính lỗi giới hạn lượt gọi (429) hoặc lỗi máy chủ (5xx) thì ngủ và thử lại
                if response.status_code in [429, 500, 502, 503, 504]:
                    time.sleep(delay)
                    delay *= 2
                    continue
                else:
                    break
            except Exception as e:
                logger.error(f"❌ Lỗi kết nối vật lý tới Gemini API: {str(e)}")
                time.sleep(delay)
                delay *= 2

        # Fallback an toàn nếu toàn bộ API thất bại
        logger.warning("⚠️ Kích hoạt chế độ Fallback Response cho sếp Park.")
        return {
            "response_vi": "Ne, sếp đang bận xử lý một số cuộc họp khẩn cấp. Cậu hỏi lại sau vài giây nữa nhé, hoặc kiểm tra lại kết nối mạng nha!",
            "korean_terms_explained": {"Ne": "Vâng, ừ"},
            "escalate": False,
            "confidence": 0.5
        }