import React from 'react'
import {load_script} from '../utils'

export default class Recaptcha extends React.Component {
  componentDidMount () {
    console.log('componentDidMount', window._grecaptcha_load_callback)
    if (window._grecaptcha_load_callback) {
      // recaptcha has already been loaded
      window._grecaptcha_load_callback()
      window.grecaptcha.reset()
      return
    }
    window._grecaptcha_load_callback = () => {
      window.grecaptcha.render('google-recaptcha', {
        sitekey: process.env.REACT_APP_RECAPTCHA_KEY,
        callback: '_grecaptcha_click_callback'
      })
    }
    window._grecaptcha_click_callback = t => this.props.callback && this.props.callback(t)
    load_script('https://www.google.com/recaptcha/api.js?onload=_grecaptcha_load_callback&render=explicit')
  }

  render () {
    return <div id="google-recaptcha"/>
  }
}
