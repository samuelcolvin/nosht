import React from 'react'
import {load_script} from '../utils'

const element_id = 'google-recaptcha'
const load_callback = 'google_recaptcha_load_callback'
const click_callback = 'google_recaptcha_click_callback'

function grecaptcha_render () {
  window.grecaptcha.render(element_id, {sitekey: process.env.REACT_APP_RECAPTCHA_KEY, callback: click_callback})
}

export default class Recaptcha extends React.Component {
  static reset () {
    try {
      grecaptcha_render()
    } catch (error) {
      // already rendered is ok, ignore
      if (error.message !== 'reCAPTCHA has already been rendered in this element') {
        throw error
      }
    }
    window.grecaptcha.reset()
  }

  componentDidMount () {
    window[click_callback] = t => this.props.callback(t)
    if (window[load_callback]) {
      // recaptcha has already been loaded
      Recaptcha.reset()
    } else {
      window[load_callback] = grecaptcha_render
      load_script(`https://www.google.com/recaptcha/api.js?onload=${load_callback}&render=explicit`)
    }
  }

  render () {
    return <div id={element_id}/>
  }
}
