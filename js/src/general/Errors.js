import React from 'react'
import {withRouter} from 'react-router-dom'

export const Error = ({error}) => {
  if (error.status === 404) {
    return <NotFound url={error.url}/>
  } else if (error.status === 401) {
    return <Loading/>
  } else {
    return (
      <div>
        <h1>Error</h1>
        <p>
          {error.msg ? error.msg.toString() : error.toString()}.
        </p>
      </div>
    )
  }
}

export const NotFound = withRouter(({url, children, location}) => (
  <div>
    <h1>Page not found</h1>
    <p>The page <code>{url || location.pathname}</code> doesn't exist.</p>
    {children}
  </div>
))

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
