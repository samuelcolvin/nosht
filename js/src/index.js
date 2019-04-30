import React from 'react'
import ReactDOM from 'react-dom'
import {BrowserRouter as Router} from 'react-router-dom'
import * as Sentry from '@sentry/browser'
import ReactGA from 'react-ga'
import BrowserUpdate from 'browser-update'
import App from './App'
import './styles/main.scss'

window.Sentry = Sentry

if (process.env.NODE_ENV === 'production') {
  Sentry.init({
    dsn: process.env.REACT_APP_SENTRY_DSN,
    release: process.env.REACT_APP_COMMIT,
    attachStacktrace: true,
  })
}
BrowserUpdate({
  required: {
    e: -4,
    f: -3,
    o: -3,
    s: -1,
    c: -3,
  },
  insecure: true,
  unsupported: true,
  api: 2019.04,
  style: 'bottom',
})
ReactGA.initialize(process.env.REACT_APP_GA_TRACKING_ID || 'UA-000000-01', {titleCase: false})
ReactDOM.render(<Router><App/></Router>, document.getElementById('root'))
