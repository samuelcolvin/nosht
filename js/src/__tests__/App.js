import React from 'react'
import ReactDOM from 'react-dom'
import {BrowserRouter as Router} from 'react-router-dom'
import App from '../App'
import {wait_for} from './setup'

test('shows highlights', async () => {
  const console_spy = jest.spyOn(global.console, 'error')
  const div = document.createElement('div')
  ReactDOM.render(<Router><App/></Router>, div)
  await wait_for(() => div.querySelectorAll('.card').length > 0)
  expect(div.querySelectorAll('.card').length).toEqual(3)
  expect(div.innerHTML).toEqual(expect.stringMatching(/Frank's Great Supper/))
  ReactDOM.unmountComponentAtNode(div)
  expect(console_spy).not.toHaveBeenCalled()
})
