import urllib.request, json

try:
    with urllib.request.urlopen("http://localhost:8000/api/welcome", timeout=5) as r:
        d = json.loads(r.read())
        print("welcome API OK, sections:", len(d.get("sections", [])))
except Exception as e:
    print("welcome API ERROR:", e)

try:
    with urllib.request.urlopen("http://localhost:8000/", timeout=5) as r:
        html = r.read().decode()
        print("index.html size:", len(html))
        print("has tpl-welcome:", "tpl-welcome" in html)
        print("has nav welcome:", "welcome" in html)
        print("has app.js:", "app.js" in html)
except Exception as e:
    print("index.html ERROR:", e)

try:
    with urllib.request.urlopen("http://localhost:8000/app.js", timeout=5) as r:
        js = r.read().decode()
        print("app.js size:", len(js))
        print("has loadWelcome:", "loadWelcome" in js)
        print("has await this.loadWelcome:", "await this.loadWelcome" in js)
        print("has async loadWelcome:", "async loadWelcome" in js)
except Exception as e:
    print("app.js ERROR:", e)
