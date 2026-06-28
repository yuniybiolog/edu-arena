def handle_google_callback(self):
    parsed = urlparse(self.path)
    query = parse_qs(parsed.query)
    code = query.get('code', [None])[0]

    if not code:
        self.send_error(400)
        return

    token_res = requests.post('https://oauth2.googleapis.com/token', data={
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code'
    })
    token_data = token_res.json()
    access_token = token_data.get('access_token')

    if not access_token:
        self.send_error(400)
        return

    user_res = requests.get('https://www.googleapis.com/oauth2/v2/userinfo', headers={
        'Authorization': f'Bearer {access_token}'
    })
    google_user = user_res.json()

    google_id = google_user.get('id')
    email = google_user.get('email')
    name = google_user.get('name')
    avatar = google_user.get('picture')

    db = get_db()
    cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute('SELECT * FROM users WHERE google_id = %s OR email = %s', (google_id, email))
    user = cur.fetchone()

    if not user:
        username = email.split('@')[0]
        cur.execute("""
            INSERT INTO users (username, name, email, google_id, avatar_url)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (username) DO UPDATE SET username = %s || '_' || LEFT(md5(random()::text), 5)
            RETURNING id, omega, kappa
        """, (username, name, email, google_id, avatar, username))
        user = cur.fetchone()
        db.commit()

    token = str(user['id'])
    cur.close()
    db.close()

    html = f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head><body>
<script>
localStorage.setItem('token', '{token}');
window.location.href = '/app';
</script>
</body></html>'''

    self.send_response(200)
    self.send_header('Content-Type', 'text/html; charset=utf-8')
    self.end_headers()
    self.wfile.write(html.encode())
