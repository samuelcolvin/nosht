import React from 'react'
import {Route, Switch, withRouter} from 'react-router-dom'

import requests from './requests'
import {sleep, load_script_callback, window_property} from './utils'
import {Error, NotFound, Loading} from './general/Errors'
import Navbar from './general/Navbar'
import Footer from './general/Footer'
import Index from './Main'
import Category from './cats/Main'
import Event from './events/Main'
import Login from './auth/Login'
import Logout from './auth/Logout'
import Signup from './auth/Signup'
import SetPassword from './auth/SetPassword'
import CreateEvent from './events/Create'
import Dashboard from './Dashboard'


const Routes = ({app}) => (
    <Switch>
      <Route exact path="/" render={() => (
        <Index setRootState={s => app.setState(s)} company={app.state.company}/>
      )} />

      <Route exact path="/login/" render={props => (
        <Login setRootState={s => app.setState(s)}
               set_message={app.set_message}
               company={app.state.company}
               {...props}/>
      )} />

      <Route exact path="/logout/" render={props => (
        <Logout setRootState={s => app.setState(s)}
                set_message={app.set_message}
                {...props}/>
      )} />

      <Route exact path="/signup/" render={props => (
        <Signup setRootState={s => app.setState(s)}
                set_message={app.set_message}
                {...props}/>
      )} />

      <Route exact path="/set-password/" render={props => (
        <SetPassword setRootState={s => app.setState(s)}
                     set_message={app.set_message}
                     {...props}/>
      )} />


      <Route path="/dashboard/" render={props => (
        <Dashboard setRootState={s => app.setState(s)}
                   user={app.state.user}
                   set_message={app.set_message}
                   company={app.state.company}
                   {...props}/>
      )} />

      <Route path="/create/" render={props => (
        <CreateEvent setRootState={s => app.setState(s)}
                     set_message={app.set_message}
                     {...props}/>
      )} />

      <Route path="/:category/:event/" render={props => (
        <Event setRootState={s => app.setState(s)}
               set_message={app.set_message}
               company={app.state.company}
               user={app.state.user}
               {...props}/>
      )} />

      <Route exact path="/:category/" render={props => (
        <Category setRootState={s => app.setState(s)}
                  company={app.state.company}
                  {...props}/>
      )} />

      <Route component={NotFound} />
    </Switch>
)

class _App extends React.Component {
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
      grecaptcha_ready: false,
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
      const company = await requests.get('')
      const user = company.user
      delete company.user
      this.setState({company, user})
    } catch (err) {
      this.setState({error: err})
    }
    await load_script_callback('https://www.google.com/recaptcha/api.js?onload=<callback-function>&render=onload')
    const grecaptcha = await window_property('grecaptcha')
    grecaptcha.render({
      sitekey: process.env.REACT_APP_RECAPTCHA_KEY,
      badge: 'bottomleft',
    })
    grecaptcha.ready(() => {
      this.setState({grecaptcha_ready: true})
    })
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
