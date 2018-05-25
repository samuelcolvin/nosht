import React, { Component } from 'react'
import {Route, Switch, withRouter } from 'react-router-dom'
import Navbar from './Navbar'

class _App extends Component {
  render () {
    return (
      <div>
        <Navbar/>
        <main className="container">
          <Switch>
            <Route exact path="/" render={props => (
              <div>
                <h1 className="mt-5">testing</h1>
                <p className="lead">this is cool.</p>
              </div>
            )} />
            <Route exact path="/foo/" render={props => (
              <div>
                <h1 className="mt-5">foo</h1>
                <p className="lead">this is cool.</p>
              </div>
            )} />

            <Route render={props => (
              <div className="box">
                <h3>Page not found</h3>
                <p>The page "{props.location.pathname}" doesn't exist.</p>
              </div>
            )} />
          </Switch>
        </main>
      </div>
    )
  }
}

export default withRouter(_App)
