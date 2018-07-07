import {load_script} from './utils'

export async function setup_siw () {
  await load_script('https://apis.google.com/js/platform.js')
  window.gapi.load('auth2', () => {
    window.gauth = window.gapi.auth2.init({
      client_id: process.env.REACT_APP_GOOGLE_SIW_CLIENT_KEY,
      scope: 'profile email',
    })
  })
  await load_script('https://connect.facebook.net/en_US/sdk.js')
  window.fbAsyncInit = () => {
    window.FB.init({
      appId: process.env.REACT_APP_FACEBOOK_SIW_APP_ID,
      cookie: true,
      xfbml: true,
      version: 'v3.0'
    })
  }
}

export function facebook_login (setRootState) {
  return new Promise(resolve => {
    window.FB.login(r => {
      if (r.status === 'connected') {
        resolve(r.authResponse)
      } else if (r.status === undefined) {
        // user probably closed the popup
        resolve()
      } else {
        console.error('facebook auth unexpected response:', r)
        setRootState({error: 'Error on facebook authentication'})
        resolve()
      }
    }, {scope: 'email'})
  })
}

export async function google_login (setRootState) {
  try {
    await window.gauth.signIn()
  }  catch (error) {
    if (error.error === 'popup_closed_by_user') {
      return
    } else {
      console.error('google auth error:', error)
      setRootState({error: 'Error on google authentication'})
      return
    }
  }
  return {id_token: window.gauth.currentUser.get().getAuthResponse().id_token}
}
