import React from 'react'
import {Route, Switch, Link} from 'react-router-dom'
import {Row, Col} from 'reactstrap'
import {NotFound} from '../utils/Errors'
import {as_title} from '../../utils'
import {EventsList, CategoriesList, UsersList} from './SettingsLists'
import {EventsDetails, CategoriesDetails, UsersDetails} from './SettingsDetails'

const PAGES = [
  {name: 'events', list_comp: EventsList, details_comp: EventsDetails},
  {name: 'categories', list_comp: CategoriesList, details_comp: CategoriesDetails},
  {name: 'users', list_comp: UsersList, details_comp: UsersDetails},
  {name: 'company', list_comp: null, details_comp: null},
  {name: 'export', list_comp: null, details_comp: null},
]

const list_uri = page => `/settings/${page.name}/`
const details_uri = page => `/settings/${page.name}/:id/`

const MenuItem = ({page, location}) => {
  const uri = list_uri(page)
  const active = location.pathname.startsWith(uri) ? ' active' : ''
  return <Link to={uri} className={'list-group-item list-group-item-action' + active}>
    {as_title(page.name)}
  </Link>
}

const RenderComp = ({page, props, parent, comp_name}) => {
  const Comp = page[comp_name]
  if (Comp) {
    return <Comp page={page}
                 match={props.match}
                 setRootState={parent.props.setRootState}
                 requests={parent.props.requests}
                 location={props.location}
                 history={props.history}/>
  }
  return <div>TODO {page.name}</div>
}

export default class Settings extends React.Component {
  constructor (props) {
    super(props)
    this.state = {finished: false}
  }

  render () {
    return (
      <Row>
        <Col md="3">
        <div className="list-group">
          {PAGES.map(p => (
            <MenuItem key={p.name} page={p} location={this.props.location}/>
          ))}
        </div>
        </Col>
        <Col md="9">
          <Switch>
            {PAGES.map(p => (
              <Route key={p.name} exact path={list_uri(p)} render={props => (
                <RenderComp page={p} props={props} parent={this} comp_name="list_comp"/>
              )} />
            ))}
            {PAGES.map(p => (
              <Route key={p.name + '-details'} path={details_uri(p)} render={props => (
                <RenderComp page={p} props={props} parent={this} comp_name="details_comp"/>
              )} />
            ))}

            <Route component={NotFound} />
          </Switch>

        </Col>
      </Row>
    )
  }
}
