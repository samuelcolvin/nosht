import React from 'react'
import {Redirect} from 'react-router'
import {Loading} from '../general/Errors'
import requests from '../requests'


export default class Logout extends React.Component {
  constructor (props) {
    super(props)
    this.state = {finished: false}
  }

  async componentDidMount () {
    try {
      await requests.post('logout/')
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    this.props.setRootState({user: null})
    this.setState({finished: true})
    this.props.set_message({icon: 'user', message: 'Logged out successfully'})
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
