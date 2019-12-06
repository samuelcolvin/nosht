import React from 'react'
import {Route, Switch, withRouter} from 'react-router-dom'
import * as Sentry from '@sentry/browser'
import ReactGA from 'react-ga'
import {library as FaLibrary} from '@fortawesome/fontawesome-svg-core'
import {far} from '@fortawesome/free-regular-svg-icons'
import {fas} from '@fortawesome/free-solid-svg-icons'
import {fab} from '@fortawesome/free-brands-svg-icons'

import {GlobalContext} from './utils/context'
import requests from './utils/requests'
import {sleep} from './utils'
import {Error, NotFound, Loading} from './general/Errors'
import Navbar from './general/Navbar'
import Footer from './general/Footer'
import Index from './Main'
import Category from './cats/Main'
import Event from './events/Main'
import Login from './auth/Login'
import Logout from './auth/Logout'
import Signup from './auth/Signup'
import RequestPasswordReset from './auth/RequestPasswordReset'
import SetPassword from './auth/SetPassword'
import CreateEvent from './events/Create'
import {UnsubscribeValid, UnsubscribeInvalid, WaitingListRemoved} from './Unsubscribe'
import Dashboard from './Dashboard'

FaLibrary.add(far, fas, fab)

const Routes = () => (
    <Switch>
      <Route exact path="/" component={Index}/>

      <Route exact path="/login/" component={Login}/>
      <Route exact path="/logout/" component={Logout}/>
      <Route exact path="/signup/" component={Signup}/>
      <Route exact path="/set-password/" component={SetPassword}/>
      <Route exact path="/password-reset/" component={RequestPasswordReset}/>

      <Route path="/dashboard/" component={Dashboard}/>
      <Route path="/create/" component={CreateEvent}/>

      <Route exact path="/waiting-list-removed/" component={WaitingListRemoved}/>
      <Route exact path="/unsubscribe-valid/" component={UnsubscribeValid}/>
      <Route exact path="/unsubscribe-invalid/" component={UnsubscribeInvalid}/>

      <Route path="/pvt/:category/:event/:sig/" component={Event}/>
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
      active_page: null,
      error: null,
      message: null,
    }
    this.setMessage = this.setMessage.bind(this)
    this.setError = this.setError.bind(this)
    this.setUser = this.setUser.bind(this)
  }

  async setMessage (message) {
    this.setState({message})
    await sleep(8000)
    this.setState({message: null})
  }

  async componentDidMount () {
    ReactGA.pageview(this.props.location.pathname + this.props.location.search)
    try {
      const company = await requests.get('')
      this.setUser(company.user)
      delete company.user
      this.setState({company})
    } catch (err) {
      this.setState({error: err})
    }
  }

  componentDidUpdate (prevProps) {
    if (this.props.location !== prevProps.location) {
      ReactGA.pageview(this.props.location.pathname + this.props.location.search)
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

  componentDidCatch (error, info) {
    Sentry.configureScope(scope => scope.setExtra('extra', info))
    Sentry.captureException(error)
    this.setState({error: error.toString()})
  }

  setError (error) {
    if (error.status === 401) {
      this.setMessage({icon: 'sign-in-alt', message: error.msg || 'Login Required'})
      this.props.history.push(`/login/?next=${encodeURIComponent(this.props.location.pathname)}`)
      return
    } else if (error.status !== 404) {
      Sentry.configureScope(scope => scope.setExtra('extra', error))
      Sentry.captureMessage(`caught error: ${error.msg || error.toString()}`, 'warning')
    }
    this.setState({error})
  }

  setUser (user) {
    this.setState({user})
    ReactGA.set({userId: user ? user.id : null})
  }

  render () {
    const ctx = {
      setRootState: s => this.setState(s),
      setMessage: msg => this.setMessage(msg),
      setError: error => this.setError(error),
      setUser: user => this.setUser(user),
      company: this.state.company,
      user: this.state.user,
    }
    return (
      <GlobalContext.Provider value={ctx}>
        <Navbar company={this.state.company}
                background={this.state.background}
                message={this.state.message}
                user={this.state.user}
                active_page={this.state.active_page}/>
        <div className="pad-footer">
          <main className="container">
            {this.state.error ?
              <Error error={this.state.error} location={this.props.location}/>
              :
              this.state.company ?
                <Routes/>
                :
                <Loading/>
            }
          </main>
        </div>
        <Footer user={ctx.user} co_footer_links={ctx.company && ctx.company.company.footer_links}/>
      </GlobalContext.Provider>
    )
  }
}
export default withRouter(App)
