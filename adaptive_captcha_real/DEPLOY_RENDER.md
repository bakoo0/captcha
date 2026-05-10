# Deploy to Render

This version does not use Node.js. It runs a FastAPI backend that serves:

- `/` demo website
- `/widget/behavior-captcha-widget.js` browser widget
- `/api/risk-score` ML risk scoring endpoint
- `/api/captcha/challenge` image challenge endpoint
- `/api/captcha/verify` verification endpoint

## 1. Push to GitHub

```bash
git init
git add .
git commit -m "Create real adaptive CAPTCHA FastAPI widget"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

## 2. Create MongoDB Atlas database

Create a free cluster and copy the connection string.

Example:

```env
MONGO_URI=mongodb+srv://USER:PASSWORD@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_DB=adaptive_captcha
```

## 3. Create Render Web Service

Choose:

```text
New -> Web Service -> Connect GitHub repository -> Runtime: Docker
```

Render will use the included `Dockerfile`.

## 4. Add Environment Variables in Render

```env
MONGO_URI=mongodb+srv://USER:PASSWORD@cluster.mongodb.net/?retryWrites=true&w=majority
MONGO_DB=adaptive_captcha
```

## 5. Test after deploy

```text
https://YOUR-APP.onrender.com/api/health
https://YOUR-APP.onrender.com/widget/behavior-captcha-widget.js
```

## 6. Connect widget to another website

```html
<div id="behavior-captcha-container"></div>

<script
  src="https://YOUR-APP.onrender.com/widget/behavior-captcha-widget.js"
  data-endpoint="https://YOUR-APP.onrender.com"
  data-site-key="my-site">
</script>
```
