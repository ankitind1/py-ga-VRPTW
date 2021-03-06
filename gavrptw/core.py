# -*- coding: utf-8 -*-

'''gavrptw/core.py'''

import os
import io
import random
from csv import DictWriter
from deap import base, creator, tools
from . import BASE_DIR
from .utils import make_dirs_for_file, exist, load_instance


def ind2route(individual, instance):
    '''gavrptw.core.ind2route(individual, instance)'''
    route = []
    vehicle_capacity = instance['vehicle_capacity']
    depart_due_time = instance['depart']['due_time']
    # Initialize a sub-route
    sub_route = []
    vehicle_load = 0
    elapsed_time = 0
    last_customer_id = 0
    for customer_id in individual:
        # Update vehicle load
        demand = instance['customer_{}'.format(customer_id)]['demand']
        updated_vehicle_load = vehicle_load + demand
        # Update elapsed time
        service_time = instance['customer_{}'.format(customer_id)]['service_time']
        return_time = instance['distance_matrix'][customer_id][0]
        updated_elapsed_time = elapsed_time + \
            instance['distance_matrix'][last_customer_id][customer_id] + service_time + return_time
        # Validate vehicle load and elapsed time
        if (updated_vehicle_load <= vehicle_capacity) and (updated_elapsed_time <= depart_due_time):
            # Add to current sub-route
            sub_route.append(customer_id)
            vehicle_load = updated_vehicle_load
            elapsed_time = updated_elapsed_time - return_time
        else:
            # Save current sub-route
            route.append(sub_route)
            # Initialize a new sub-route and add to it
            sub_route = [customer_id]
            vehicle_load = demand
            elapsed_time = instance['distance_matrix'][0][customer_id] + service_time
        # Update last customer ID
        last_customer_id = customer_id
    if sub_route != []:
        # Save current sub-route before return if not empty
        route.append(sub_route)
    return route


def print_route(route, merge=False):
    '''gavrptw.core.print_route(route, merge=False)'''
    route_str = '0'
    sub_route_count = 0
    for sub_route in route:
        sub_route_count += 1
        sub_route_str = '0'
        for customer_id in sub_route:
            sub_route_str = sub_route_str + ' - ' + str(customer_id)
            route_str = route_str + ' - ' + str(customer_id)
        sub_route_str = sub_route_str + ' - 0'
        if not merge:
            print('  Vehicle {}\'s route: {}'.format(sub_route_count, sub_route_str))
        route_str = route_str + ' - 0'
    if merge:
        print(route_str)


def eval_vrptw(individual, instance, unit_cost=1.0, init_cost=0, wait_cost=0, delay_cost=0):
    '''gavrptw.core.eval_vrptw(individual, instance,
                                unit_cost=1.0, init_cost=0, wait_cost=0, delay_cost=0)'''
    total_cost = 0
    route = ind2route(individual, instance)
    total_cost = 0
    for sub_route in route:
        sub_route_time_cost = 0
        sub_route_distance = 0
        elapsed_time = 0
        last_customer_id = 0
        for customer_id in sub_route:
            # Calculate section distance
            distance = instance['distance_matrix'][last_customer_id][customer_id]
            # Update sub-route distance
            sub_route_distance = sub_route_distance + distance
            # Calculate time cost
            arrival_time = elapsed_time + distance
            time_cost = wait_cost * \
                max(instance['customer_{}'.format(customer_id)]['ready_time'] - arrival_time, 0) + \
                delay_cost * \
                max(arrival_time - instance['customer_{}'.format(customer_id)]['due_time'], 0)
            # Update sub-route time cost
            sub_route_time_cost = sub_route_time_cost + time_cost
            # Update elapsed time
            elapsed_time = arrival_time + \
                instance['customer_{}'.format(customer_id)]['service_time']
            # Update last customer ID
            last_customer_id = customer_id
        # Calculate transport cost
        sub_route_distance = sub_route_distance + instance['distance_matrix'][last_customer_id][0]
        sub_route_transport_cost = init_cost + unit_cost * sub_route_distance
        # Obtain sub-route cost
        sub_route_cost = sub_route_time_cost + sub_route_transport_cost
        # Update total cost
        total_cost = total_cost + sub_route_cost
    fitness = 1.0 / total_cost
    return (fitness, )


def cx_partialy_matched(ind1, ind2):
    '''gavrptw.core.cx_partialy_matched(ind1, ind2)'''
    size = min(len(ind1), len(ind2))
    cxpoint1, cxpoint2 = sorted(random.sample(range(size), 2))
    temp1 = ind1[cxpoint1:cxpoint2+1] + ind2
    temp2 = ind1[cxpoint1:cxpoint2+1] + ind1
    ind1 = []
    for gene in temp1:
        if gene not in ind1:
            ind1.append(gene)
    ind2 = []
    for gene in temp2:
        if gene not in ind2:
            ind2.append(gene)
    return ind1, ind2


def mut_inverse_indexes(individual):
    '''gavrptw.core.mut_inverse_indexes(individual)'''
    start, stop = sorted(random.sample(range(len(individual)), 2))
    individual = individual[:start] + individual[stop:start-1:-1] + individual[stop+1:]
    return (individual, )


def run_gavrptw(instance_name, unit_cost, init_cost, wait_cost, delay_cost, ind_size, pop_size, \
            cx_pb, mut_pb, n_gen, export_csv=False, customize_data=False):
    '''gavrptw.core.run_gavrptw(instance_name, unit_cost, init_cost, wait_cost, delay_cost,
                ind_size, pop_size, cx_pb, mut_pb, n_gen, export_csv=False, customize_data=False)'''
    if customize_data:
        json_data_dir = os.path.join(BASE_DIR, 'data', 'json_customize')
    else:
        json_data_dir = os.path.join(BASE_DIR, 'data', 'json')
    json_file = os.path.join(json_data_dir, '{}.json'.format(instance_name))
    instance = load_instance(json_file=json_file)
    if instance is None:
        return
    creator.create('FitnessMax', base.Fitness, weights=(1.0,))
    creator.create('Individual', list, fitness=creator.FitnessMax)
    toolbox = base.Toolbox()
    # Attribute generator
    toolbox.register('indexes', random.sample, range(1, ind_size + 1), ind_size)
    # Structure initializers
    toolbox.register('individual', tools.initIterate, creator.Individual, toolbox.indexes)
    toolbox.register('population', tools.initRepeat, list, toolbox.individual)
    # Operator registering
    toolbox.register(
        'evaluate',
        eval_vrptw,
        instance=instance,
        unit_cost=unit_cost,
        init_cost=init_cost,
        wait_cost=wait_cost,
        delay_cost=delay_cost
    )
    toolbox.register('select', tools.selRoulette)
    toolbox.register('mate', cx_partialy_matched)
    toolbox.register('mutate', mut_inverse_indexes)
    pop = toolbox.population(n=pop_size)
    # Results holders for exporting results to CSV file
    csv_data = []
    print('Start of evolution')
    # Evaluate the entire population
    fitnesses = list(map(toolbox.evaluate, pop))
    for ind, fit in zip(pop, fitnesses):
        ind.fitness.values = fit
    print('  Evaluated {} individuals'.format(len(pop)))
    # Begin the evolution
    for gen in range(n_gen):
        print('-- Generation {} --'.format(gen))
        # Select the next generation individuals
        offspring = toolbox.select(pop, len(pop))
        # Clone the selected individuals
        offspring = list(map(toolbox.clone, offspring))
        # Apply crossover and mutation on the offspring
        for child1, child2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < cx_pb:
                toolbox.mate(child1, child2)
                del child1.fitness.values
                del child2.fitness.values
        for mutant in offspring:
            if random.random() < mut_pb:
                toolbox.mutate(mutant)
                del mutant.fitness.values
        # Evaluate the individuals with an invalid fitness
        invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
        fitnesses = map(toolbox.evaluate, invalid_ind)
        for ind, fit in zip(invalid_ind, fitnesses):
            ind.fitness.values = fit
        print('  Evaluated {} individuals'.format(len(invalid_ind)))
        # The population is entirely replaced by the offspring
        pop[:] = offspring
        # Gather all the fitnesses in one list and print the stats
        fits = [ind.fitness.values[0] for ind in pop]
        length = len(pop)
        mean = sum(fits) / length
        sum2 = sum(x*x for x in fits)
        std = abs(sum2 / length - mean**2)**0.5
        print('  Min {}'.format(min(fits)))
        print('  Max {}'.format(max(fits)))
        print('  Avg {}'.format(mean))
        print('  Std {}'.format(std))
        # Write data to holders for exporting results to CSV file
        if export_csv:
            csv_row = {
                'generation': gen,
                'evaluated_individuals': len(invalid_ind),
                'min_fitness': min(fits),
                'max_fitness': max(fits),
                'avg_fitness': mean,
                'std_fitness': std,
            }
            csv_data.append(csv_row)
    print('-- End of (successful) evolution --')
    best_ind = tools.selBest(pop, 1)[0]
    print('Best individual: {}'.format(best_ind))
    print('Fitness: {}'.format(best_ind.fitness.values[0]))
    print_route(ind2route(best_ind, instance))
    print('Total cost: {}'.format(1 / best_ind.fitness.values[0]))
    if export_csv:
        csv_file_name = '{}_uC{}_iC{}_wC{}_dC{}_iS{}_pS{}_cP{}_mP{}_nG{}.csv'.format(
            instance_name,
            unit_cost,
            init_cost,
            wait_cost,
            delay_cost,
            ind_size,
            pop_size,
            cx_pb,
            mut_pb,
            n_gen
        )
        csv_file = os.path.join(BASE_DIR, 'results', csv_file_name)
        print('Write to file: {}'.format(csv_file))
        make_dirs_for_file(path=csv_file)
        if not exist(path=csv_file, overwrite=True):
            with io.open(csv_file, 'wt', newline='') as file_object:
                fieldnames = [
                    'generation',
                    'evaluated_individuals',
                    'min_fitness',
                    'max_fitness',
                    'avg_fitness',
                    'std_fitness',
                ]
                writer = DictWriter(file_object, fieldnames=fieldnames, dialect='excel')
                writer.writeheader()
                for csv_row in csv_data:
                    writer.writerow(csv_row)
