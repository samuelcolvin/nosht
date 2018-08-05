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
import {GlobalContext} from './context'


const Routes = () => (
    <Switch>
      <Route exact path="/" component={Index}/>

      <Route exact path="/login/" component={Login}/>
      <Route exact path="/logout/" component={Logout}/>
      <Route exact path="/signup/" component={Signup}/>
      <Route exact path="/set-password/" component={SetPassword}/>

      <Route path="/dashboard/" component={Dashboard}/>
      <Route path="/create/" component={CreateEvent}/>

      <Route path="/:category/:event/" component={Event}/>
      <Route exact path="/:category/" component={Category}/>

      <Route component={NotFound}/>
    </Switch>
)

class App extends React.Component {
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
    const ctx = {
      setRootState: s => this.setState(s),
      set_message: (...args) => this.set_message(...args),
      company: this.state.company,
      user: this.state.user,
    }
    return (
      <GlobalContext.Provider value={ctx}>
        <Navbar company={this.state.company}
                background={this.state.background}
                extra_menu={this.state.extra_menu}
                message={this.state.message}
                active_page={this.state.active_page}/>
        <main className="container">
          {this.state.error ? <Error error={this.state.error}
                                     location={this.props.location}
                                     set_message={this.set_message}/>
            : this.state.company ? <Routes/>
              : <Loading/>}
        </main>
        <Footer user={this.state.user}/>
      </GlobalContext.Provider>
    )
  }
}

export default withRouter(App)
