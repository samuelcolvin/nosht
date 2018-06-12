import React from 'react'
import {Redirect} from 'react-router'

export class Error extends React.Component {
  componentWillMount () {
    if (this.props.error.status === 401) {
      this.props.set_message({icon: 'ban', message: this.props.error.user_msg || 'Login Required'})
    } else if (this.props.error.status !== 404) {
      console.warn('caught error:', this.props.error)
    }
  }

  render () {
    const error = this.props.error
    if (error.status === 404) {
      return <NotFound location={this.props.location} url={error.url}/>
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

export const NotFound = ({location, url}) => (
  <div>
    <h1>Page not found</h1>
    <p>The page <code>{url || location.pathname}</code> doesn't exist.</p>
  </div>
)

export const Loading = () => (
  <small className="text-muted">loading...</small>
)
