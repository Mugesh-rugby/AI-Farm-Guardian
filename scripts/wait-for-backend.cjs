const http = require('node:http')

const backendUrl = 'http://127.0.0.1:8000/health'
const timeoutMs = 60000
const retryDelayMs = 500
const startedAt = Date.now()
let waitingMessageShown = false

function waitForBackend() {
  const request = http.get(backendUrl, (response) => {
    response.resume()
    if (response.statusCode === 200) {
      console.log('Backend is ready; starting the frontend.')
      process.exit(0)
      return
    }
    retry()
  })

  request.setTimeout(1000, () => request.destroy())
  request.on('error', retry)
}

function retry() {
  if (Date.now() - startedAt >= timeoutMs) {
    console.error('Backend did not become ready. Check the MySQL connection and backend output.')
    process.exit(1)
    return
  }

  if (!waitingMessageShown) {
    console.log('Waiting for the backend to connect to MySQL...')
    waitingMessageShown = true
  }
  setTimeout(waitForBackend, retryDelayMs)
}

waitForBackend()
