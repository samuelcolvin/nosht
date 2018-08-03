import React from 'react'
import {Route, Switch, Link} from 'react-router-dom'
import {Row, Col} from 'reactstrap'
import {NotFound} from './general/Errors'
import {as_title} from './utils'
import {EventsList, EventsDetails} from './events/Dashboard'
import {UsersList, UsersDetails} from './users/Dashboard'
import {CategoriesList, CategoriesDetails} from './cats/Dashboard'

const list_uri = page => `/dashboard/${page.name}/`
const list_match_uri = page => `/dashboard/${page.name}/(add/)?`
const details_uri = page => `/dashboard/${page.name}/:id/`

const MenuItem = ({page, location}) => {
  const uri = list_uri(page)
  const active = location.pathname.startsWith(uri) ? ' active' : ''
  return <Link to={uri} className={'list-group-item list-group-item-action' + active}>
    {page.title || as_title(page.name)}
  </Link>
}

const RenderComp = ({page, route_props, parent, comp_name}) => {
  const Comp = page[comp_name]
  if (Comp) {
    return <Comp {...parent.props} {...route_props} page={page}/>
  }
  return <div>TODO {page.name}</div>
}

export default class Settings extends React.Component {
  constructor (props) {
    super(props)
    this.state = {finished: false}
  }

  render () {
    let pages = [
      {name: 'events', title: 'My Events', list_comp: EventsList, details_comp: EventsDetails},
      {name: 'account', title: 'Account', list_comp: null, details_comp: null},
    ]
    if (this.props.user && this.props.user.role === 'admin') {
      pages = [
        {name: 'events', list_comp: EventsList, details_comp: EventsDetails},
        {name: 'categories', list_comp: CategoriesList, details_comp: CategoriesDetails},
        {name: 'users', list_comp: UsersList, details_comp: UsersDetails},
        {name: 'company', list_comp: null, details_comp: null},
        {name: 'export', list_comp: null, details_comp: null},
      ]
    }
    return (
      <Row>
        <Col md="3">
        <div className="list-group mb-2">
          {pages.map(p => (
            <MenuItem key={p.name} page={p} location={this.props.location}/>
          ))}
        </div>
        </Col>
        <Col md="9">
          <Switch>
            {pages.map(p => (
              <Route key={p.name} exact path={list_match_uri(p)} render={props => (
                <RenderComp page={p} route_props={props} parent={this} comp_name="list_comp"/>
              )} />
            ))}
            {pages.map(p => (
              <Route key={p.name + '-details'} path={details_uri(p)} render={props => (
                <RenderComp page={p} route_props={props} parent={this} comp_name="details_comp"/>
              )} />
            ))}

            <Route component={NotFound} />
          </Switch>

        </Col>
      </Row>
    )
  }
}
