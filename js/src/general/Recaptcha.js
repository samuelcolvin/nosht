import React from 'react'
import {load_script} from '../utils'

export default class Recaptcha extends React.Component {
  static reset () {
    window._grecaptcha_load_callback()
    window.grecaptcha.reset()
  }

  componentDidMount () {
    window._grecaptcha_click_callback = t => this.props.callback(t)
    if (window._grecaptcha_load_callback) {
      // recaptcha has already been loaded
      Recaptcha.reset()
    } else {
      window._grecaptcha_load_callback = () => {
        window.grecaptcha.render('google-recaptcha', {
          sitekey: process.env.REACT_APP_RECAPTCHA_KEY,
          callback: '_grecaptcha_click_callback'
        })
      }
      load_script('https://www.google.com/recaptcha/api.js?onload=_grecaptcha_load_callback&render=explicit')
    }
  }

  render () {
    return <div id="google-recaptcha"/>
  }
}
