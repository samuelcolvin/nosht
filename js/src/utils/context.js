import React from 'react'
import {get_component_name} from './index'

export const GlobalContext = React.createContext({})

export default WrappedComponent => {
  const WithContext = (props) => (
    <GlobalContext.Consumer>
      {ctx => <WrappedComponent {...props} ctx={ctx}/>}
    </GlobalContext.Consumer>
  )
  WithContext.displayName = `WithContext(${get_component_name(WrappedComponent)})`
  return WithContext
}
