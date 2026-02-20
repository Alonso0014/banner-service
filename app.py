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
    if 'candidates' not in data:
        raise Exception(f'Gemini 에러: {data}')
    return data['candidates'][0]['content']['parts'][0]['text']

def add_cors(response):
    origin = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Origin'] = origin if origin else '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response

@app.after_request
def after_request(response):
    return add_cors(response)

@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    return jsonify({}), 200

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.json
    width, height = data.get('width'), data.get('height')
    purpose = data.get('purpose')
    requirements = data.get('requirements', '')

    prompt = f"""당신은 디지털 광고 배너 디자인 전문가입니다.
아래 조건에 맞는 배너 디자인 스펙을 JSON으로만 응답해주세요. 마크다운 없이 순수 JSON만 출력하세요.

- 사이즈: {width}x{height}px
- 용도: {purpose}
- 요구사항: {requirements}

다음 JSON 구조로 응답:
{{
  "width": {width},
  "height": {height},
  "background": {{"r": 0.0, "g": 0.0, "b": 0.0}},
  "gradient": null,
  "shapes": [
    {{"name": "Button", "type": "RECTANGLE", "x": 0, "y": 0, "width": 200, "height": 50, "color": {{"r":1,"g":1,"b":1}}, "opacity": 1, "corner_radius": 8}}
  ],
  "texts": [
    {{"name": "Headline", "text": "카피 텍스트", "x": 40, "y": 60, "width": {int(width)-80}, "size": 48, "weight": 700, "font": "Inter", "align": "LEFT", "color": {{"r":1,"g":1,"b":1}}}}
  ],
  "design_brief": "디자인 의도 설명"
}}

중요: font 값은 반드시 "Inter" 로만 사용하세요. 다른 폰트는 지원하지 않습니다.
gradient를 사용할 경우 background는 null로 하고 gradient는 아래 형식:
[{{"position": 0, "color": {{"r":0.1,"g":0.1,"b":0.9,"a":1}}}}, {{"position": 1, "color": {{"r":0.5,"g":0.0,"b":0.8,"a":1}}}}]

색상값은 0.0~1.0 범위의 float. 배너 용도와 요구사항에 맞게 레이아웃, 색상, 카피를 창의적으로 구성하세요."""

    raw = call_gemini(prompt)

    import json, re
    clean = re.sub(r'```(?:json)?', '', raw).strip().rstrip('`').strip()
    try:
        spec = json.loads(clean)
        if isinstance(spec, list):
            spec = spec[0]
    except Exception as e:
        print(f'파싱 실패: {e}')
        print(f'RAW: {raw[:500]}')
        return jsonify({'status': 'error', 'error': '스펙 파싱 실패', 'raw': raw}), 500

    return jsonify({'status': 'success', 'design_spec': spec, 'design_brief': spec.get('design_brief', '')})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    message, context = data.get('message'), data.get('context', '')

    prompt = f"""당신은 배너 디자인 수정을 도와주는 전문가입니다.
현재 배너 컨텍스트: {context}
사용자 수정 요청: {message}

구체적인 수정 방법을 알려주세요."""

    reply = call_gemini(prompt)
    return jsonify({'status': 'success', 'reply': reply})

if __name__ == '__main__':
    app.run(debug=True, port=8080)
    