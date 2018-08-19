import {spawn} from 'child_process'
import {library as FaLibrary} from '@fortawesome/fontawesome-svg-core'
import {far} from '@fortawesome/free-regular-svg-icons'
import {fas} from '@fortawesome/free-solid-svg-icons'
import {fab} from '@fortawesome/free-brands-svg-icons'
import {sleep} from '../utils'
import r from '../utils/requests'

FaLibrary.add(far, fas, fab)

export function Server () {
  this.proc = null
  this.start = async function start () {
    this.proc = spawn('./src/__tests__/run_server.py', {stdio: 'inherit'})
    for (let i=0; i < 10; i++) {
      await sleep(500)
      try {
        await r.get('http://localhost:8000/api/')
      } catch (e) {
        continue
      }
      return
    }
  }

  this.stop = function stop () {
    this.proc.kill('SIGTERM')
  }
}

export const wait_for = async fn => {
  for (let i=0; i < 20; i++) {
    await sleep(25)
    const r = fn()
    if (r) {
      return r
    }
  }
  throw Error('wait_for failed, function never returned true')
}

const server = new Server()
beforeAll(() => server.start())
afterAll(() => server.stop())

test('server running', async () => {
  expect(Number.isInteger(server.proc.pid)).toEqual(true)
  expect(server.proc.exitCode).toEqual(null)
})
