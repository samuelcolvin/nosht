import React, { Component } from 'react'
import {Route, Switch, withRouter } from 'react-router-dom'

import {get, post} from '../utils'
import Navbar from './Navbar'
import Index from './Index'

class _App extends Component {
  constructor (props) {
    super(props)
    this.state = {
      page_title: null,
      company_data: null,
      loaded: false,
      error: null,
    }
    this.requests = {
      get: async (...args) => get(...args),
      post: async (...args) => post(...args),
    }
  }

  async componentDidMount () {
    try {
      const data = await this.requests.get('')
      console.log('data', data)
      this.setState({company_data: data, loaded: true})
    } catch (err) {
      this.setState({error: err})
    }
  }

  componentDidUpdate () {
    let next_title = process.env.REACT_APP_SITE_NAME
    if (this.state.page_title) {
      next_title += ' - ' + this.state.page_title
    }
    if (next_title !== document.title) {
      document.title = next_title
    }
  }

  render () {
    return (
      <div>
        <Navbar company_data={this.state.company_data}/>
        <main className="container">
          <Switch>
            <Route exact path="/" render={() => (
              <Index setRootState={s => this.setState(s)} company_data={this.state.company_data}/>
            )} />
            <Route exact path="/foo/" render={props => (
              <div>
                <h1>foo</h1>
                <p className="lead">this is cool.</p>
              </div>
            )} />

            <Route render={props => (
              <div>
                <h1>Page not found</h1>
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
