import {load_script, window_property} from '../utils'

export async function setup_siw () {
  await load_script('https://apis.google.com/js/platform.js')
  const gapi = await window_property('gapi')
  gapi.load('auth2', () => {
    window.gauth = gapi.auth2.init({
      client_id: process.env.REACT_APP_GOOGLE_SIW_CLIENT_KEY,
      scope: 'profile email',
    })
  })
}

export async function google_login (setError) {
  const gauth = await window_property('gauth')
  try {
    await gauth.signIn()
  }  catch (error) {
    if (error.error === 'popup_closed_by_user') {
      return
    } else {
      console.error('google auth error:', error)
      setError('Error on google authentication')
      return
    }
  }
  return {id_token: gauth.currentUser.get().getAuthResponse().id_token}
}
