import React from 'react'
import ReactDOM from 'react-dom'
import {BrowserRouter as Router} from 'react-router-dom'
import Raven from 'raven-js'
import App from './App'
import './styles/main.scss'

if (process.env.NODE_ENV === 'production') {
  // TODO could add release here
  Raven.config(process.env.REACT_APP_SENTRY_DSN).install()
}
ReactDOM.render(<Router><App /></Router>, document.getElementById('root'))
