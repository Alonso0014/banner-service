from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import os
import requests

load_dotenv()

app = Flask(__name__, static_folder='static')

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_URL = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}'

FIGMA_API_BASE = 'https://api.figma.com/v1'

def call_gemini(prompt):
    res = requests.post(GEMINI_URL, json={
        'contents': [{'parts': [{'text': prompt}]}]
    })
    data = res.json()
    if 'candidates' not in data:
        raise Exception(f'Gemini 에러: {data}')
    return data['candidates'][0]['content']['parts'][0]['text']

def figma_headers(token):
    return {'X-Figma-Token': token, 'Content-Type': 'application/json'}

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})

# Figma 토큰 유효성 검사
@app.route('/api/figma/verify', methods=['POST'])
def figma_verify():
    token = request.json.get('token')
    if not token:
        return jsonify({'status': 'error', 'error': '토큰 없음'}), 400
    res = requests.get(f'{FIGMA_API_BASE}/me', headers=figma_headers(token))
    if res.status_code == 200:
        data = res.json()
        return jsonify({'status': 'success', 'name': data.get('handle', ''), 'email': data.get('email', '')})
    return jsonify({'status': 'error', 'error': '유효하지 않은 토큰'}), 400

# Figma 배너 생성 (하나의 파일에 프레임 추가)
@app.route('/api/figma/create', methods=['POST'])
def figma_create():
    data = request.json
    token = data.get('figma_token')
    design_spec = data.get('design_spec')
    file_key = data.get('file_key')  # 기존 파일 키 (없으면 새 파일 생성)

    if not token:
        return jsonify({'status': 'error', 'error': 'Figma 토큰 없음'}), 400

    w = design_spec.get('width', 1080)
    h = design_spec.get('height', 1080)
    bg = design_spec.get('background', {'r': 0.1, 'g': 0.1, 'b': 0.2})
    texts = design_spec.get('texts', [])
    shapes = design_spec.get('shapes', [])
    gradient = design_spec.get('gradient')

    if gradient:
        bg_paint = {
            'type': 'GRADIENT_LINEAR',
            'gradientHandlePositions': [
                {'x': 0, 'y': 0}, {'x': 1, 'y': 1}, {'x': 0, 'y': 1}
            ],
            'gradientStops': gradient
        }
    else:
        bg_paint = {'type': 'SOLID', 'color': bg}

    children = []
    for s in shapes:
        children.append({
            'type': s.get('type', 'RECTANGLE'),
            'name': s.get('name', 'Shape'),
            'x': s.get('x', 0), 'y': s.get('y', 0),
            'width': s.get('width', 100), 'height': s.get('height', 100),
            'fills': [{'type': 'SOLID', 'color': s.get('color', {'r':1,'g':1,'b':1}), 'opacity': s.get('opacity', 1)}],
            'cornerRadius': s.get('corner_radius', 0)
        })
    for t in texts:
        children.append({
            'type': 'TEXT',
            'name': t.get('name', 'Text'),
            'x': t.get('x', 0), 'y': t.get('y', 0),
            'width': t.get('width', w - 80),
            'characters': t.get('text', ''),
            'style': {
                'fontFamily': t.get('font', 'Inter'),
                'fontSize': t.get('size', 24),
                'fontWeight': t.get('weight', 400),
                'textAlignHorizontal': t.get('align', 'LEFT'),
                'fills': [{'type': 'SOLID', 'color': t.get('color', {'r':1,'g':1,'b':1})}]
            }
        })

    frame_node = {
        'type': 'FRAME',
        'name': f'Banner_{w}x{h}',
        'x': 0, 'y': 0,
        'width': w, 'height': h,
        'fills': [bg_paint],
        'children': children
    }

    # 기존 파일이 없으면 새 파일 생성
    if not file_key:
        res = requests.post(
            f'{FIGMA_API_BASE}/files',
            headers=figma_headers(token),
            json={'name': '배너 작업 파일', 'nodes': [frame_node]}
        )
        if res.status_code not in (200, 201):
            return jsonify({'status': 'error', 'error': res.text}), 400
        result = res.json()
        file_key = result.get('key')
    else:
        # 기존 파일에 프레임 추가 - 기존 프레임 위치 파악 후 오른쪽에 배치
        file_res = requests.get(f'{FIGMA_API_BASE}/files/{file_key}', headers=figma_headers(token))
        if file_res.status_code == 200:
            file_data = file_res.json()
            existing = file_data.get('document', {}).get('children', [{}])[0].get('children', [])
            max_x = max((n.get('absoluteBoundingBox', {}).get('x', 0) + n.get('absoluteBoundingBox', {}).get('width', 0) for n in existing), default=0)
            frame_node['x'] = max_x + 40  # 기존 프레임 우측에 40px 간격
        
        res = requests.post(
            f'{FIGMA_API_BASE}/files/{file_key}/nodes',
            headers=figma_headers(token),
            json={'nodes': [frame_node]}
        )
        if res.status_code not in (200, 201):
            return jsonify({'status': 'error', 'error': res.text}), 400

    return jsonify({
        'status': 'success',
        'file_key': file_key,
        'url': f'https://www.figma.com/file/{file_key}'
    })

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

gradient를 사용할 경우 background는 null로 하고 gradient는 아래 형식:
[{{"position": 0, "color": {{"r":0.1,"g":0.1,"b":0.9,"a":1}}}}, {{"position": 1, "color": {{"r":0.5,"g":0.0,"b":0.8,"a":1}}}}]

색상값은 0.0~1.0 범위의 float. 배너 용도와 요구사항에 맞게 레이아웃, 색상, 카피를 창의적으로 구성하세요."""

    raw = call_gemini(prompt)

    import json, re
    clean = re.sub(r'```(?:json)?', '', raw).strip().rstrip('`').strip()
    try:
        spec = json.loads(clean)
    except:
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