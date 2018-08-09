import React from 'react'
import WithContext from './utils/context'

export const UnsubscribeValid = WithContext(({ctx}) => (
  <div>
    <h1>Thank you for Unsubscribing</h1>
    <p>You will not receive any more emails from {ctx.company.company.name}.</p>
  </div>
))

export const UnsubscribeInvalid = () => (
  <div>
    <h1>Invalid Unsubscrible link</h1>
    <p>The link you followed was invalid.</p>
  </div>
)
