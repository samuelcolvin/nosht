import React from 'react'
import {get_component_name} from './utils'

export const GlobalContext = React.createContext(
  {
    setRootState: s => console.error('global context not setup for "setRootState"', s),
    setMessage: msg => console.error('global context not setup for "setMessage"', msg),
    setError: err => console.error('global context not setup for "setError"', err),
    company: {},
    user: {},
  }
)

export default WrappedComponent => {
  const ContextComponent = (props) => (
    <GlobalContext.Consumer>
      {ctx => <WrappedComponent {...props} ctx={ctx} />}
    </GlobalContext.Consumer>
  )
  ContextComponent.displayName = `ContextComponent(${get_component_name(WrappedComponent)})`
  return ContextComponent
}
