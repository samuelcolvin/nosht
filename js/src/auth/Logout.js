import React from 'react'
import {Redirect} from 'react-router'
import WithContext from '../context'
import {Loading} from '../general/Errors'
import requests from '../requests'

class Logout extends React.Component {
  constructor (props) {
    super(props)
    this.state = {finished: false}
  }

  async componentDidMount () {
    try {
      await requests.post('logout/')
    } catch (error) {
      this.props.ctx.setRootState({error})
      return
    }
    this.props.ctx.setRootState({user: null})
    this.setState({finished: true})
    this.props.ctx.set_message({icon: 'user', message: 'Logged out successfully'})
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
