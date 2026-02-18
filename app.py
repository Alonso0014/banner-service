from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import os
import requests

load_dotenv()

app = Flask(__name__, static_folder='static')

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_URL = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}'

def call_gemini(prompt):
    res = requests.post(GEMINI_URL, json={
        'contents': [{'parts': [{'text': prompt}]}]
    })
    data = res.json()
    print('Gemini 응답:', data)  # 디버그용
    if 'candidates' not in data:
        raise Exception(f'Gemini 에러: {data}')
    return data['candidates'][0]['content']['parts'][0]['text']

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.json
    width = data.get('width')
    height = data.get('height')
    purpose = data.get('purpose')
    requirements = data.get('requirements', '')

    prompt = f"""
당신은 디지털 광고 배너 디자인 전문가입니다.
아래 조건에 맞는 배너 디자인 지시서를 작성해주세요.

- 사이즈: {width}x{height}px
- 용도: {purpose}
- 요구사항: {requirements}

다음 형식으로 답변해주세요:
1. 레이아웃 구성
2. 색상 팔레트 (hex 코드 포함)
3. 타이포그래피
4. 핵심 카피 제안
5. 이미지/그래픽 요소
"""
    reply = call_gemini(prompt)
    return jsonify({'status': 'success', 'design_brief': reply})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    message = data.get('message')
    context = data.get('context', '')

    prompt = f"""
당신은 배너 디자인 수정을 도와주는 전문가입니다.
현재 배너 컨텍스트: {context}
사용자 수정 요청: {message}

구체적인 수정 방법을 알려주세요.
"""
    reply = call_gemini(prompt)
    return jsonify({'status': 'success', 'reply': reply})

if __name__ == '__main__':
    app.run(debug=True, port=8080)