import requests
from PIL import Image
from io import BytesIO

img = Image.new('RGB', (512, 512), color='#d9c7b8')
buffer = BytesIO()
img.save(buffer, format='PNG')
files = {'photo': ('test.png', buffer.getvalue(), 'image/png')}
data = {'prompt': 'executive linkedin headshot with navy blazer and soft studio lighting'}
response = requests.post('http://127.0.0.1:8000/api/linkedin-photo/generate', files=files, data=data)
print('Status:', response.status_code)
print('Body:', response.text)
