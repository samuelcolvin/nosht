import 'babel-polyfill'
import 'react-app-polyfill/ie11'

import React from 'react'
import ReactDOM from 'react-dom'
import {BrowserRouter as Router} from 'react-router-dom'
import * as Sentry from '@sentry/browser'
import ReactGA from 'react-ga'
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
ReactGA.initialize(process.env.REACT_APP_GA_TRACKING_ID || 'UA-000000-01', {titleCase: false})
ReactDOM.render(<Router><App/></Router>, document.getElementById('root'))
