// Build the frontend and serve it from FastAPI in mock mode (Playwright webServer).
import { execSync, spawn } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '../..')
const port = process.env.PORT ?? '8000'
const live = process.env.LIVE === '1'

function findUv() {
  const candidates = [process.env.UV, 'uv']
  if (process.platform === 'win32') {
    const appdata = process.env.APPDATA ?? path.join(os.homedir(), 'AppData', 'Roaming')
    for (const v of ['Python313', 'Python312']) candidates.push(path.join(appdata, 'Python', v, 'Scripts', 'uv.exe'))
    candidates.push(path.join(os.homedir(), '.local', 'bin', 'uv.exe'))
  }
  for (const c of candidates.filter(Boolean)) {
    try {
      execSync(`"${c}" --version`, { stdio: 'ignore' })
      return c
    } catch {
      /* try next */
    }
  }
  throw new Error('uv not found: install it or set UV=/path/to/uv')
}

if (!process.env.SKIP_BUILD) execSync('npm run build', { cwd: path.join(root, 'frontend'), stdio: 'inherit' })
const dataDir = path.join(root, 'data', live ? 'e2e-live' : 'e2e')
fs.rmSync(dataDir, { recursive: true, force: true })

const env = {
  ...process.env,
  MOCK_LLM: live ? '0' : '1',
  DATA_DIR: dataDir,
  RATE_LIMIT_ASK: live ? '10/minute' : '100000/minute',
  RATE_LIMIT_UPLOAD: live ? '5/minute' : '100000/minute',
  MAX_QUESTIONS_PER_DOC: live ? '50' : '100000',
  MOCK_TTFT_MS: process.env.MOCK_TTFT_MS ?? '400',
  PYTHONUTF8: '1',
}
const child = spawn(findUv(), ['run', 'uvicorn', 'app.main:app', '--port', port], {
  cwd: path.join(root, 'backend'),
  env,
  stdio: 'inherit',
})
const stop = () => child.kill()
process.on('SIGINT', stop)
process.on('SIGTERM', stop)
process.on('exit', stop)
child.on('exit', (code) => process.exit(code ?? 0))
