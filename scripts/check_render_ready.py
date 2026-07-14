import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import app
    print('app import ok')
    with app.app.test_client() as client:
        resp = client.get('/login')
        print('GET /login', resp.status_code)
        if resp.status_code != 200:
            print(resp.data[:200])
        resp2 = client.post('/entrar', data={'identifier': 'admin@naturviagens.pt', 'password': '1234'}, follow_redirects=False)
        print('POST /entrar', resp2.status_code, resp2.headers.get('Location'))
        with client.session_transaction() as sess:
            print('session', sess.get('user_id'), sess.get('user_role'))
except Exception as exc:
    import traceback
    traceback.print_exc()
    raise
