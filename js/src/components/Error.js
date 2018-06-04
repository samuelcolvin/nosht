import React from 'react'

const Error = ({error}) => (
  <div>
    <h3>Error:</h3>
    <p>
      {error.toString()}
      <code>{JSON.stringify(error, null, 2)}</code>
    </p>
  </div>
)

export default Error
