import React, { Component } from 'react'
import {Route, Switch, withRouter } from 'react-router-dom'

import {get, post} from '../utils'
import { Error, NotFound, Loading } from './utils/Errors'
import Navbar from './Navbar'
import Footer from './Footer'
import Index from './pages/Index'
import Category from './pages/Category'
import Event from './pages/Event'


const Routes = ({app}) => (
    <Switch>
      <Route exact path="/" render={() => (
        <Index setRootState={s => app.setState(s)} company_data={app.state.company_data}/>
      )} />

      <Route exact={true} path="/:category/:event/" render={props => (
        <Event setRootState={s => app.setState(s)}
               requests={app.requests}
               company_data={app.state.company_data}
               location={props.location}
               match={props.match}/>
      )} />

      <Route exact={true} path="/:category/" render={props => (
        <Category setRootState={s => app.setState(s)}
                  requests={app.requests}
                  company_data={app.state.company_data}
                  location={props.location}
                  match={props.match}/>
      )} />

      <Route render={props => (
        <NotFound location={props.props}/>
      )} />
    </Switch>
)

class _App extends Component {
  constructor (props) {
    super(props)
    this.state = {
      page_title: null,
      company_data: null,
      background: null,
      extra_menu: null,
      active_page: null,
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
      this.setState({company_data: data})
    } catch (err) {
      this.setState({error: err})
    }
  }

  componentDidUpdate (prevProps) {
    if (this.props.location !== prevProps.location) {
      window.scrollTo(0, 0)
      if (this.state.error) {
        this.setState({error: null})
      }
    }

    let next_title = this.state.company_data ? this.state.company_data.company.name : ''
    if (this.state.page_title) {
      next_title += ' - ' + this.state.page_title
    }
    if (next_title !== document.title) {
      document.title = next_title
    }
  }

  render () {
    return [
      <Navbar key={1}
              company_data={this.state.company_data}
              background={this.state.background}
              extra_menu={this.state.extra_menu}
              active_page={this.state.active_page}/>,
      <main key={2} className="container">
        {this.state.error ? <Error error={this.state.error} location={this.props.location}/>
          : this.state.company_data ? <Routes app={this}/>
            : <Loading/>}
      </main>,
      <Footer key={3}/>
    ]
  }
}

export default withRouter(_App)
