import React, {Component} from 'react'
import {Redirect} from 'react-router'

export class Error extends Component {
  componentWillMount () {
    if (this.props.error.status === 401) {
      this.props.set_message({icon: 'ban', message: this.props.error.user_msg || 'Login Required'})
    } else if (this.props.error.status !== 404) {
      console.warn('caught error:', this.props)
    }
  }

  render () {
    const error = this.props.error
    if (error.status === 404) {
      return <NotFound location={this.props.location}/>
    } else if (error.status === 401 && this.props.location.pathname !== '/login/') {
      return <Redirect to="/login/"/>
    } else {
      return (
        <div>
          <h1>Error</h1>
          <p>
            {error.user_msg || error.toString()}.
          </p>
        </div>
      )
    }
  }
}

export const NotFound = ({location}) => (
  <div>
    <h1>Page not found</h1>
    <p>The page <code>{location.pathname}</code> doesn't exist.</p>
  </div>
)

export const Loading = () => (
  <small className="text-muted">loading...</small>
)
