import requests
from database import conectar


def get_first_cliente_id():
    db = conectar()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM clientes ORDER BY id ASC LIMIT 1")
    row = cursor.fetchone()
    try:
        cursor.close()
        db.close()
    except Exception:
        pass
    if not row:
        return None
    # row may be sqlite Row or tuple
    return row[0]


def test_create_viagem():
    s = requests.Session()
    login = s.post('http://127.0.0.1:5000/entrar', data={'identifier': 'admin@naturviagens.pt', 'password': '1234'})
    print('login status', login.status_code)
    cliente_id = get_first_cliente_id()
    if cliente_id is None:
        print('Nenhum cliente encontrado para usar em viagem')
        return
    resp = s.post('http://127.0.0.1:5000/admin/viagens/novo', data={
        'destino': 'Teste Auto',
        'data_inicio': '01/10/2026',
        'data_fim': '05/10/2026',
        'cliente_id': str(cliente_id),
    }, allow_redirects=False)
    print('create viagem status', resp.status_code)
    print('Location header:', resp.headers.get('Location'))


if __name__ == '__main__':
    test_create_viagem()
