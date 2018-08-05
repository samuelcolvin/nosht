import React from 'react'
import WithContext from '../utils/context'
import {Redirect} from 'react-router'
import Raven from 'raven-js'

class Error_ extends React.Component {
  componentWillMount () {
    if (this.props.error.status === 401) {
      this.props.ctx.setMessage({icon: 'ban', message: this.props.error.user_msg || 'Login Required'})
    } else if (this.props.error.status !== 404) {
      console.warn('caught error:', this.props.error)
      Raven.captureMessage(`caught error: ${this.props.error.user_msg}`, {
        stacktrace: true,
        level: 'warning',
        extra: {error: this.props.error}
      })
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
export const Error = WithContext(Error_)

export const NotFound = ({location, url, children}) => (
  <div>
    <h1>Page not found</h1>
    <p>The page <code>{url || location.pathname}</code> doesn't exist.</p>
    {children}
  </div>
)

export const Loading = ({children}) => (
  <small className="text-muted">
    loading...
    {children}
  </small>
)


export const Waiting = () => (
  <div className="wait-circle">
    {[...Array(12).keys()].map(i => (
      <div key={i} className={`el-${i}`}/>
    ))}
  </div>
)
