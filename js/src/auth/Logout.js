import React from 'react'
import {Redirect} from 'react-router'
import ReactGA from 'react-ga'
import WithContext from '../utils/context'
import {Loading} from '../general/Errors'
import requests from '../utils/requests'

class Logout extends React.Component {
  constructor (props) {
    super(props)
    this.state = {finished: false}
  }

  async componentDidMount () {
    try {
      await requests.post('logout/')
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.props.ctx.setUser(null)
    window.sessionStorage.clear()
    this.setState({finished: true})
    ReactGA.event({category: 'auth', action: 'auth-logout'})
    this.props.ctx.setMessage({icon: 'user', message: 'Logged out successfully'})
  }

  render () {
    if (this.state.finished) {
      return <Redirect to="/"/>
    }
    return (
      <Loading/>
    )
  }
}
export default WithContext(Logout)
