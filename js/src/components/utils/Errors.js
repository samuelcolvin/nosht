import React from 'react'

export const Error = ({error, location}) => {
  console.warn('caught error:', error)
  return (
    <div>
      <h1>Error</h1>
      <p>
        {error.user_msg || error.toString()}.
      </p>
    </div>
  )
}

export const NotFound = ({location}) => (
  <div>
    <h1>Page not found</h1>
    <p>The page "{location.pathname}" doesn't exist.</p>
  </div>
)

export const Loading = () => (
  <small className="text-muted">loading...</small>
)
