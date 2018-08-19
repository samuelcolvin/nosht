import React from 'react'
import ReactDOM from 'react-dom'
import {BrowserRouter as Router} from 'react-router-dom'
import {spawn} from 'child_process'
import App from '../App'
import {sleep} from '../utils'
import r from '../utils/requests'

let server

beforeAll(async () => {
  server = spawn('./src/__tests__/run_server.py', {stdio: 'inherit'})
  for (let i=0; i < 10; i++) {
    await sleep(500)
    try {
      await r.get('http://localhost:8000/api/')
    } catch (e) {
      continue
    }
    return
  }
})

afterAll(() => {
  server.kill('SIGTERM')
})

test('server running', async () => {
  expect(Number.isInteger(server.pid)).toEqual(true)
  expect(server.exitCode).toEqual(null)
})

test('renders without crashing', () => {
  const div = document.createElement('div')
  ReactDOM.render(<Router><App/></Router>, div)
  ReactDOM.unmountComponentAtNode(div)
})
