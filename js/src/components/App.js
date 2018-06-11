import React, {Component} from 'react'
import {Route, Switch, withRouter} from 'react-router-dom'

import {get, post, sleep} from '../utils'
import {Error, NotFound, Loading} from './utils/Errors'
import Navbar from './Navbar'
import Footer from './Footer'
import Index from './pages/Index'
import Category from './pages/Category'
import Event from './pages/Event'
import Login from './pages/Login'
import Logout from './pages/Logout'
import Settings from './pages/Settings'


const Routes = ({app}) => (
    <Switch>
      <Route exact path="/" render={() => (
        <Index setRootState={s => app.setState(s)} company={app.state.company}/>
      )} />

      <Route exact path="/login/" render={() => (
        <Login setRootState={s => app.setState(s)}
               requests={app.requests}
               set_message={app.set_message}
               company={app.state.company}/>
      )} />

      <Route exact path="/logout/" render={() => (
        <Logout setRootState={s => app.setState(s)}
                set_message={app.set_message}
                requests={app.requests}/>
      )} />

      <Route path="/settings/" render={props => (
        <Settings setRootState={s => app.setState(s)}
                  set_message={app.set_message}
                  location={props.location}
                  requests={app.requests}/>
      )} />

      <Route exact path="/:category/:event/" render={props => (
        <Event setRootState={s => app.setState(s)}
               requests={app.requests}
               company={app.state.company}
               location={props.location}
               match={props.match}/>
      )} />

      <Route exact path="/:category/" render={props => (
        <Category setRootState={s => app.setState(s)}
                  requests={app.requests}
                  company={app.state.company}
                  location={props.location}
                  match={props.match}/>
      )} />

      <Route render={props => (
        <NotFound location={props.location}/>
      )} />
    </Switch>
)

class _App extends Component {
  constructor (props) {
    super(props)
    this.state = {
      page_title: null,
      company: null,
      user: null,
      background: null,
      extra_menu: null,
      active_page: null,
      error: null,
      message: null,
    }
    this.requests = {
      get: async (...args) => get(...args),
      post: async (...args) => post(...args),
    }
    this.set_message = this.set_message.bind(this)
  }

  async set_message (message, time) {
    this.setState({message})
    await sleep(time || 5000)
    this.setState({message: null})
  }

  async componentDidMount () {
    try {
      const company = await this.requests.get('')
      const user = company.user
      delete company.user
      this.setState({company, user})
    } catch (err) {
      this.setState({error: err})
    }
  }

  componentDidUpdate (prevProps) {
    if (this.props.location !== prevProps.location) {
      if (window.scrollY > 400) {
        window.scrollTo(0, 0)
      }
      if (this.state.error) {
        this.setState({error: null})
      }
    }

    let next_title = this.state.company ? this.state.company.company.name : ''
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
              company={this.state.company}
              background={this.state.background}
              extra_menu={this.state.extra_menu}
              message={this.state.message}
              active_page={this.state.active_page}/>,
      <main key={2} className="container">
        {this.state.error ? <Error error={this.state.error}
                                   location={this.props.location}
                                   set_message={this.set_message}/>
          : this.state.company ? <Routes app={this}/>
            : <Loading/>}
      </main>,
      <Footer key={3} user={this.state.user}/>
    ]
  }
}

export default withRouter(_App)
