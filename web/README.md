# QuantPair web

Next.js front end for QuantPair: the landing page (`/`) and the research terminal (`/app/*`).
It talks to the Python API in `../api/server.py`, which must be running on port 8000.

```bash
npm install
npm run dev        # http://localhost:3000
```

Set `NEXT_PUBLIC_API_URL` to point at a different API host. See the repository README for the full setup.
