import React from 'react'
import ReactDOM from 'react-dom'
import {MemoryRouter, Route} from 'react-router-dom'
import Event from '../events/Main'
import {wait_for} from './setup'
import {GlobalContext} from "../utils/context"

test('renders public event', async () => {
  const console_spy = jest.spyOn(global.console, 'error')
  const div = document.createElement('div')
  const events = []
  const ctx = {
    setRootState: s => events.push(s),
    setMessage: (...args) => events.push({message: args}),
    setError: error => events.push({error}),
    setUser: user => events.push({user}),
    company: {
      company: {
        currency: 'gbp'
      }
    },
    user: null,
  }
  ReactDOM.render(
    <MemoryRouter initialEntries={['/foo/bar']}>
      <GlobalContext.Provider value={ctx}>
        <Route path="/:category/:event/" component={Event}/>
      </GlobalContext.Provider>
    </MemoryRouter>, div)
  await wait_for(() => div.querySelectorAll('.btn-primary').length > 0)

  expect(div.innerHTML).toEqual(expect.stringMatching(/<h1>Frank's Great Supper<\/h1>/))
  ReactDOM.unmountComponentAtNode(div)
  expect(console_spy).not.toHaveBeenCalled()
})
