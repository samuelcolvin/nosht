import React from 'react'
import {get_component_name} from './utils'

export const GlobalContext = React.createContext(
  {
    setRootState: (...args) => console.error('global context not setup for "setRootState"', args),
    set_message: (...args) => console.error('global context not setup for "set_message"', args),
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
